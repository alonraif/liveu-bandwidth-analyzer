# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start Commands

Start the full application stack:
```bash
cp .env.example .env
docker-compose up
```

Access the application at http://localhost

## Development Commands

### Frontend (React)
```bash
cd frontend
npm start      # Development server
npm run build  # Production build
```

### Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload  # Development server
```

### Parser Worker
```bash
cd parser
pip install -r requirements.txt
python src/worker.py  # Start worker process
```

## Architecture Overview

This is a cloud-based log parsing platform for LiveU support staff with a microservices architecture:

### Core Components
- **Frontend**: React app with Recharts for data visualization and file upload via react-dropzone
- **Backend**: FastAPI service handling uploads, session management, and data queries
- **Parser**: Python worker processes that extract bandwidth/RTT metrics from compressed logs
- **Database**: TimescaleDB (PostgreSQL + time-series extension) for metrics storage
- **Queue**: Redis for job queuing between backend and parser workers
- **Storage**: MinIO (S3-compatible) for raw log file storage
- **Proxy**: Nginx for routing and serving static files

### Data Flow
1. User uploads compressed log files (.tar.bz2, .bz2) via React frontend
2. Backend stores file in MinIO and queues parsing job in Redis
3. Parser workers extract bandwidth metrics using regex patterns and save to TimescaleDB
4. Frontend polls session status and displays interactive time-series charts

### Key Files
- `docker-compose.yml`: Complete stack orchestration with all services
- `scripts/init-db.sql`: Database schema with TimescaleDB hypertable setup
- `backend/src/main.py`: FastAPI endpoints for upload, status, and data retrieval
- `parser/src/worker.py`: Log parsing worker with configurable regex patterns
- `frontend/src/App.js`: Main React component with upload and visualization

### Database Schema
- `sessions`: Track upload sessions and processing status
- `bandwidth_metrics`: Time-series data (session_id, time, modem_id, bandwidth_mbps, rtt_ms)

### Parser Configuration
The parser uses regex patterns in `parser/src/worker.py` that need customization for different log formats:
- `bandwidth`: Extracts modem ID and bandwidth values
- `rtt`: Extracts RTT measurements
- `timestamp`: Parses log timestamps

### Environment Configuration
Copy `.env.example` to `.env` and modify for different environments. Key variables:
- Database, Redis, and MinIO connection strings
- Storage type (minio for local, S3 for production)
- AWS credentials for production S3 usage