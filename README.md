# NGL - Next Gen LULA

## Overview
Cloud-based, dockerized log parsing platform for LiveU support staff.

## Quick Start
```bash
cp .env.example .env
docker-compose up
open http://localhost
```

## Features
- Upload compressed log files (.tar.bz2, .bz2)
- Extract bandwidth and RTT metrics
- Interactive time-series visualization
- Per-modem and aggregated views
- Export capabilities
- **Messages Log Merger**: Extract and merge all messages.log files in chronological order

## Architecture
- Frontend: React + Recharts
- Backend: FastAPI
- Parser: Python workers
- Database: TimescaleDB
- Queue: Redis
- Storage: MinIO/S3

## Log Merger Feature

The integrated log merger allows you to:

1. **Upload compressed log archives** (.tar.bz2, .bz2, .tar)
2. **Automatically extract and merge** all messages.log files (including rotated .gz files)
3. **Sort chronologically** - Orders all log entries by timestamp (oldest first)
4. **Download merged file** - Get a single text file with all messages in order

### Usage

1. Go to the "Log Merger" tab in the web interface
2. Upload your compressed log archive
3. Click "Download Merged Logs" to get the chronologically sorted file

### Supported Formats

- Compressed archives: `.tar.bz2`, `.bz2`, `.tar`
- Log files: `messages.log`, `messages.log.1.gz`, `messages.log.2.gz`, etc.
- Timestamp formats: Syslog, ISO8601, and common variations