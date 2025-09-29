"""
Log Merger Utility for NGL - Next Gen LULA
Extracts and merges messages.log files in chronological order
"""

import os
import gzip
import tempfile
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Any
import re
from datetime import datetime
import tarfile
import bz2


def extract_timestamp(line: str, current_year: int = None) -> datetime:
    """Extract timestamp from log line. Supports various formats including ISO 8601."""
    if current_year is None:
        current_year = datetime.now().year

    timestamp_patterns = [
        # ISO 8601 with timezone and microseconds: 2025-09-23T12:23:36.779174+00:00
        r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+[+-]\d{2}:\d{2})',
        # ISO 8601 with timezone: 2025-09-23T12:23:36+00:00
        r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})',
        # ISO 8601 with microseconds: 2025-09-23T12:23:36.779174
        r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)',
        # Basic ISO 8601: 2024-01-15T10:30:45
        r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',
        # Standard datetime: 2024-01-15 10:30:45
        r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
        # Syslog format: Jan 15 10:30:45
        r'^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})',
    ]

    for pattern in timestamp_patterns:
        match = re.match(pattern, line.strip())
        if match:
            timestamp_str = match.group(1)
            try:
                formats = [
                    '%Y-%m-%dT%H:%M:%S.%f%z',      # 2025-09-23T12:23:36.779174+00:00
                    '%Y-%m-%dT%H:%M:%S%z',         # 2025-09-23T12:23:36+00:00
                    '%Y-%m-%dT%H:%M:%S.%f',        # 2025-09-23T12:23:36.779174
                    '%Y-%m-%dT%H:%M:%S',           # 2024-01-15T10:30:45
                    '%Y-%m-%d %H:%M:%S',           # 2024-01-15 10:30:45
                    '%b %d %H:%M:%S',              # Jan 15 10:30:45
                ]
                for fmt in formats:
                    try:
                        parsed_dt = datetime.strptime(timestamp_str, fmt)
                        # For syslog format without year, add current year
                        if fmt == '%b %d %H:%M:%S':
                            parsed_dt = parsed_dt.replace(year=current_year)
                        # Convert to naive datetime (remove timezone info for comparison)
                        if parsed_dt.tzinfo is not None:
                            parsed_dt = parsed_dt.replace(tzinfo=None)
                        return parsed_dt
                    except ValueError:
                        continue
            except ValueError:
                pass

    return datetime.fromtimestamp(0)


def parse_date_range(start_str: str, end_str: str) -> tuple:
    """Parse start and end date strings into datetime objects."""
    start_dt = None
    end_dt = None

    if start_str:
        try:
            # Handle different input formats
            parts = start_str.split()
            if len(parts) == 1:  # Date only (YYYY-MM-DD)
                start_dt = datetime.strptime(start_str, '%Y-%m-%d')
            elif len(parts) == 2:  # Date and time without seconds (YYYY-MM-DD HH:MM)
                start_dt = datetime.strptime(start_str, '%Y-%m-%d %H:%M')
            else:  # Date and time with seconds (YYYY-MM-DD HH:MM:SS)
                start_dt = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S')
        except ValueError as e:
            print(f"Invalid start date format: {start_str} - {e}")

    if end_str:
        try:
            # Handle different input formats
            parts = end_str.split()
            if len(parts) == 1:  # Date only
                end_dt = datetime.strptime(end_str, '%Y-%m-%d')
                # Set to end of day
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
            elif len(parts) == 2:  # Date and time without seconds (YYYY-MM-DD HH:MM)
                end_dt = datetime.strptime(end_str, '%Y-%m-%d %H:%M')
            else:  # Date and time with seconds (YYYY-MM-DD HH:MM:SS)
                end_dt = datetime.strptime(end_str, '%Y-%m-%d %H:%M:%S')
        except ValueError as e:
            print(f"Invalid end date format: {end_str} - {e}")

    return start_dt, end_dt


def is_timestamp_in_range(timestamp: datetime, start_dt: datetime, end_dt: datetime) -> bool:
    """Check if timestamp falls within the specified date range."""
    # Exclude lines with invalid timestamps when filtering is enabled
    if timestamp.year <= 1970:  # Invalid timestamp
        return False  # Exclude lines with invalid timestamps when date filtering is active

    if start_dt and timestamp < start_dt:
        return False

    if end_dt and timestamp > end_dt:
        return False

    return True


def get_messages_log_files(log_dir: str) -> List[Tuple[str, int]]:
    """Get all messages.log files with their rotation numbers."""
    files = []
    log_path = Path(log_dir)

    current_log = log_path / "messages.log"
    if current_log.exists():
        files.append((str(current_log), 0))

    for file_path in log_path.glob("messages.log.*.gz"):
        match = re.search(r'messages\.log\.(\d+)\.gz$', file_path.name)
        if match:
            rotation_num = int(match.group(1))
            files.append((str(file_path), rotation_num))

    files.sort(key=lambda x: x[1], reverse=True)
    return files


def read_log_file(file_path: str) -> List[str]:
    """Read log file (compressed or uncompressed) and return lines."""
    lines = []

    try:
        if file_path.endswith('.gz'):
            with gzip.open(file_path, 'rt', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    return lines


def extract_archive(archive_path: str, extract_to: str) -> str:
    """Extract archive file and return the extraction directory."""
    print(f"Extracting archive: {archive_path}")

    if archive_path.endswith('.tar.bz2'):
        print("Detected .tar.bz2 format")
        with tarfile.open(archive_path, 'r:bz2') as tar:
            tar.extractall(extract_to)
    elif archive_path.endswith('.bz2'):
        print("Detected .bz2 format, checking if it's a tar archive...")
        # Try to open as tar.bz2 first (many .bz2 files are actually tar.bz2)
        try:
            with tarfile.open(archive_path, 'r:bz2') as tar:
                print("Successfully opened as tar.bz2")
                tar.extractall(extract_to)
        except tarfile.ReadError:
            print("Not a tar archive, treating as single compressed file")
            with bz2.open(archive_path, 'rb') as source:
                with open(os.path.join(extract_to, 'extracted'), 'wb') as target:
                    shutil.copyfileobj(source, target)
    elif archive_path.endswith('.tar'):
        print("Detected .tar format")
        with tarfile.open(archive_path, 'r') as tar:
            tar.extractall(extract_to)
    else:
        raise ValueError(f"Unsupported archive format: {archive_path}")

    return extract_to


def merge_messages_logs(
    archive_path: str,
    start_datetime: str = None,
    end_datetime: str = None
) -> Dict[str, Any]:
    """
    Extract and merge all messages.log files from an archive.
    Optionally filter by date range.
    Returns merged content and metadata.
    """
    try:
        print(f"Processing archive: {archive_path}")
        if start_datetime:
            print(f"Start datetime filter: {start_datetime}")
        if end_datetime:
            print(f"End datetime filter: {end_datetime}")

        # Parse date range
        start_dt, end_dt = parse_date_range(start_datetime, end_datetime)
        if start_dt:
            print(f"Parsed start datetime: {start_dt}")
        if end_dt:
            print(f"Parsed end datetime: {end_dt}")

        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"Using temp directory: {temp_dir}")

            # Extract archive
            extract_dir = extract_archive(archive_path, temp_dir)
            print(f"Extracted to: {extract_dir}")

            # List all files to debug
            print("Files in extracted archive:")
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    print(f"  {os.path.join(root, file)}")

            # Find log directory (look for messages.log files)
            log_dirs = []
            for root, dirs, files in os.walk(extract_dir):
                messages_files = [f for f in files if f.startswith('messages.log')]
                if messages_files:
                    log_dirs.append(root)
                    print(f"Found messages.log files in {root}: {messages_files}")

            if not log_dirs:
                return {
                    "success": False,
                    "error": "No messages.log files found in archive",
                    "content": "",
                    "metadata": {}
                }

            # Use the first directory found with messages.log files
            log_directory = log_dirs[0]

            # Get all messages.log files
            log_files = get_messages_log_files(log_directory)

            if not log_files:
                return {
                    "success": False,
                    "error": "No messages.log files found",
                    "content": "",
                    "metadata": {}
                }

            # Process all log files
            all_lines = []
            filtered_count = 0
            total_lines = 0
            included_count = 0

            for file_path, rotation_num in log_files:
                lines = read_log_file(file_path)

                for line in lines:
                    if line.strip():
                        total_lines += 1
                        timestamp = extract_timestamp(line)

                        # Debug first few timestamps
                        if total_lines <= 3:
                            print(f"Sample timestamp extracted: {timestamp} from line: {line[:100]}")

                        # Apply date range filtering if specified
                        if start_dt or end_dt:
                            # Only include lines with valid timestamps that fall within range
                            if timestamp.year > 1970 and is_timestamp_in_range(timestamp, start_dt, end_dt):
                                all_lines.append((timestamp, line.rstrip(), file_path, rotation_num))
                                included_count += 1
                                # Debug first few included lines
                                if included_count <= 3:
                                    print(f"Included line: {timestamp} - {line[:100]}")
                            else:
                                filtered_count += 1
                                # Debug first few filtered lines
                                if filtered_count <= 3:
                                    if timestamp.year <= 1970:
                                        print(f"Filtered out (invalid timestamp): {timestamp} - {line[:100]}")
                                    else:
                                        print(f"Filtered out (out of range): {timestamp} - {line[:100]}")
                        else:
                            all_lines.append((timestamp, line.rstrip(), file_path, rotation_num))

            print(f"Total log lines processed: {total_lines}")
            print(f"Lines included after filtering: {len(all_lines)}")
            if filtered_count > 0:
                print(f"Lines filtered out: {filtered_count}")

            # Sort by timestamp
            all_lines.sort(key=lambda x: x[0])

            # Build merged content header
            header_lines = [
                f"# Merged messages.log files in chronological order",
            ]

            if start_dt or end_dt:
                header_lines.append(f"# Date range filter applied:")
                if start_dt:
                    header_lines.append(f"#   From: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                if end_dt:
                    header_lines.append(f"#   To: {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                header_lines.append(f"#   Lines included: {len(all_lines)} of {total_lines}")

            content_lines = header_lines + [
                f"# Generated from {len(log_files)} log files",
                f"# Total entries: {len(all_lines)}",
                "#" + "="*80,
                ""
            ]

            current_source = None
            for timestamp, line, source_file, rotation_num in all_lines:
                if source_file != current_source:
                    content_lines.append(f"\n# Source: {os.path.basename(source_file)} (rotation {rotation_num})")
                    current_source = source_file

                content_lines.append(line)

            merged_content = "\n".join(content_lines)

            # Calculate statistics
            earliest_timestamp = all_lines[0][0] if all_lines else None
            latest_timestamp = all_lines[-1][0] if all_lines else None

            metadata = {
                "total_files": len(log_files),
                "total_entries": len(all_lines),
                "total_lines_processed": total_lines,
                "lines_filtered_out": filtered_count,
                "files_processed": [os.path.basename(f[0]) for f in log_files],
                "time_range": {
                    "earliest": earliest_timestamp.isoformat() if earliest_timestamp and earliest_timestamp.year > 1970 else None,
                    "latest": latest_timestamp.isoformat() if latest_timestamp and latest_timestamp.year > 1970 else None
                },
                "filter_applied": {
                    "start_datetime": start_dt.isoformat() if start_dt else None,
                    "end_datetime": end_dt.isoformat() if end_dt else None
                },
                "extraction_directory": log_directory
            }

            return {
                "success": True,
                "content": merged_content,
                "metadata": metadata
            }

    except Exception as e:
        print(f"Error in merge_messages_logs: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Error processing archive: {str(e)}",
            "content": "",
            "metadata": {}
        }