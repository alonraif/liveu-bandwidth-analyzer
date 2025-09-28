import redis
import asyncpg
import json
import bz2
import tarfile
import re
import asyncio
import os
from datetime import datetime
from minio import Minio
import tempfile

class BandwidthParser:
    def __init__(self):
        self.redis_client = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://redis:6379")
        )
        self.minio_client = Minio(
            os.getenv("MINIO_ENDPOINT", "minio:9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            secure=False
        )
        self.db_url = os.getenv("DATABASE_URL")
        
        # Patterns for LiveU modem statistics log format
        self.patterns = {
            'modem_stats': re.compile(
                r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+[+-]\d{2}:\d{2})'  # timestamp
                r'.*?Modem Statistics for modem (\d+):'  # modem number
                r'.*?potentialBW (\d+(?:\.\d+)?)(\w+bps)'  # bandwidth and unit
                r'.*?loss \((\d+(?:\.\d+)?)%\)'  # packet loss
                r'.*?extrapolated smooth upstream delay \((\d+)ms\)'  # upstream delay
                r'.*?shortest round trip delay \((\d+)ms\)'  # shortest RTT
                r'.*?extrapolated smooth round trip delay \((\d+)ms\)'  # smooth RTT
                r'.*?minimum smooth round trip delay \((\d+)ms\)'  # min RTT
                r'.*'  # Match any remaining content (like the file path)
            ),
            'timestamp': re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+[+-]\d{2}:\d{2})')
        }
    
    async def process_job(self, job_data):
        session_id = job_data['session_id']

        try:
            print(f"Processing session {session_id}")

            await self.update_session_status(session_id, 'processing')

            with tempfile.NamedTemporaryFile(suffix='.tar.bz2') as tmp_file:
                self.minio_client.fget_object(
                    'logs',
                    job_data['object_name'],
                    tmp_file.name
                )

                metrics = await self.parse_log_file(tmp_file.name)

                # Apply time range filtering if specified
                time_range = job_data.get('time_range', {})
                if time_range and (time_range.get('start') or time_range.get('end')):
                    metrics = self.filter_metrics_by_time_range(metrics, time_range)

                if metrics:
                    await self.save_metrics(session_id, metrics)
                    await self.update_session_status(
                        session_id, 'completed', metrics_count=len(metrics)
                    )
                else:
                    await self.update_session_status(
                        session_id, 'completed', metrics_count=0
                    )
                
        except Exception as e:
            print(f"Error: {str(e)}")
            await self.update_session_status(session_id, 'failed', error_message=str(e))
    
    async def parse_log_file(self, file_path):
        metrics = []

        try:
            # Try as tar.bz2 first
            with tarfile.open(file_path, 'r:bz2') as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        f = tar.extractfile(member)
                        if f:
                            file_content = f.read()

                            # Check if this is a gzipped file
                            if member.name.endswith('.gz'):
                                try:
                                    import gzip
                                    content = gzip.decompress(file_content).decode('utf-8', errors='ignore')
                                    metrics.extend(self.parse_content(content))
                                except:
                                    # If gzip decompression fails, try as regular content
                                    content = file_content.decode('utf-8', errors='ignore')
                                    metrics.extend(self.parse_content(content))
                            else:
                                # Regular file, not gzipped
                                content = file_content.decode('utf-8', errors='ignore')
                                metrics.extend(self.parse_content(content))
        except:
            # Fall back to plain bz2 if tar.bz2 fails
            try:
                with bz2.open(file_path, 'rt', errors='ignore') as f:
                    content = f.read()
                    metrics.extend(self.parse_content(content))
            except:
                # Last resort: try as regular file
                with open(file_path, 'r', errors='ignore') as f:
                    content = f.read()
                    metrics.extend(self.parse_content(content))

        return metrics
    
    def convert_bandwidth_to_mbps(self, value, unit):
        """Convert bandwidth value to Mbps"""
        value = float(value)
        unit = unit.lower()

        if unit == 'kbps':
            return value / 1000
        elif unit == 'mbps':
            return value
        elif unit == 'gbps':
            return value * 1000
        elif unit == 'bps':
            return value / 1000000
        else:
            return value  # Default to Mbps if unknown

    def parse_timestamp(self, timestamp_str):
        """Parse timestamp with timezone support"""
        try:
            # Remove timezone info for storage (keep as naive datetime)
            if '+' in timestamp_str:
                timestamp_str = timestamp_str.split('+')[0]
            elif timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1]

            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            return None

    def parse_content(self, content):
        metrics = []
        lines = content.split('\n')

        for line in lines:
            # Look for modem statistics lines
            modem_match = self.patterns['modem_stats'].search(line)
            if modem_match:
                timestamp_str = modem_match.group(1)
                modem_id = int(modem_match.group(2))
                bandwidth_value = float(modem_match.group(3))
                bandwidth_unit = modem_match.group(4)
                packet_loss = float(modem_match.group(5))
                upstream_delay = int(modem_match.group(6))
                shortest_rtt = int(modem_match.group(7))
                smooth_rtt = int(modem_match.group(8))
                min_rtt = int(modem_match.group(9))

                timestamp = self.parse_timestamp(timestamp_str)
                if timestamp:
                    metrics.append({
                        'time': timestamp,
                        'modem_id': modem_id,
                        'bandwidth_mbps': self.convert_bandwidth_to_mbps(bandwidth_value, bandwidth_unit),
                        'packet_loss_percent': packet_loss,
                        'upstream_delay_ms': upstream_delay,
                        'shortest_rtt_ms': shortest_rtt,
                        'smooth_rtt_ms': smooth_rtt,
                        'min_rtt_ms': min_rtt
                    })

        return metrics

    def filter_metrics_by_time_range(self, metrics, time_range):
        """Filter metrics by the specified time range"""
        if not time_range:
            return metrics

        start_time = None
        end_time = None

        if time_range.get('start'):
            try:
                start_time = datetime.fromisoformat(time_range['start'])
            except ValueError:
                print(f"Invalid start time format: {time_range['start']}")

        if time_range.get('end'):
            try:
                end_time = datetime.fromisoformat(time_range['end'])
            except ValueError:
                print(f"Invalid end time format: {time_range['end']}")

        if not start_time and not end_time:
            return metrics

        filtered_metrics = []
        for metric in metrics:
            metric_time = metric['time']

            # Check if metric falls within the time range
            if start_time and metric_time < start_time:
                continue
            if end_time and metric_time > end_time:
                continue

            filtered_metrics.append(metric)

        print(f"Time range filtering: {len(metrics)} -> {len(filtered_metrics)} metrics")
        return filtered_metrics

    async def save_metrics(self, session_id, metrics):
        conn = await asyncpg.connect(self.db_url)
        try:
            records = [
                (
                    session_id,
                    m['time'],
                    m['modem_id'],
                    m['bandwidth_mbps'],
                    m['packet_loss_percent'],
                    m['upstream_delay_ms'],
                    m['shortest_rtt_ms'],
                    m['smooth_rtt_ms'],
                    m['min_rtt_ms']
                )
                for m in metrics
            ]

            await conn.executemany("""
                INSERT INTO bandwidth_metrics
                (session_id, time, modem_id, bandwidth_mbps, packet_loss_percent,
                 upstream_delay_ms, shortest_rtt_ms, smooth_rtt_ms, min_rtt_ms)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT DO NOTHING
            """, records)
        finally:
            await conn.close()
    
    async def update_session_status(self, session_id, status, **kwargs):
        conn = await asyncpg.connect(self.db_url)
        try:
            if 'metrics_count' in kwargs:
                await conn.execute("""
                    UPDATE sessions
                    SET status = $1, processed_at = NOW(), metrics_count = $3
                    WHERE session_id = $2
                """, status, session_id, kwargs['metrics_count'])
            elif 'error_message' in kwargs:
                await conn.execute("""
                    UPDATE sessions
                    SET status = $1, processed_at = NOW(), error_message = $3
                    WHERE session_id = $2
                """, status, session_id, kwargs['error_message'])
            else:
                await conn.execute("""
                    UPDATE sessions
                    SET status = $1, processed_at = NOW()
                    WHERE session_id = $2
                """, status, session_id)
        finally:
            await conn.close()
    
    def run(self):
        print("Starting parser worker...")
        while True:
            try:
                job = self.redis_client.brpop('parse_queue', timeout=5)
                if job:
                    asyncio.run(self.process_job(json.loads(job[1])))
            except Exception as e:
                print(f"Worker error: {e}")

if __name__ == "__main__":
    BandwidthParser().run()