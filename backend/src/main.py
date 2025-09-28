from fastapi import FastAPI, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
import asyncpg
import redis
import json
import uuid
from datetime import datetime
from typing import Optional
import os
from minio import Minio
import io
import tempfile
try:
    from .log_merger import merge_messages_logs
except ImportError:
    from log_merger import merge_messages_logs

app = FastAPI(title="LiveU Bandwidth Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))
minio_client = Minio(
    os.getenv("MINIO_ENDPOINT", "minio:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    secure=False
)

db_pool = None

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(
        os.getenv("DATABASE_URL"),
        min_size=5,
        max_size=20
    )
    
    if not minio_client.bucket_exists("logs"):
        minio_client.make_bucket("logs")

@app.get("/")
async def root():
    return {"message": "LiveU Bandwidth Analyzer API", "version": "1.0.0"}

@app.post("/api/upload")
async def upload_log(
    file: UploadFile,
    ticket_id: Optional[str] = Form(None),
    time_start: Optional[str] = Form(None),
    time_end: Optional[str] = Form(None)
):
    """Upload a log file for processing"""
    if not file.filename.endswith(('.tar.bz2', '.bz2', '.tar')):
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    session_id = str(uuid.uuid4())
    
    file_data = await file.read()
    object_name = f"raw/{session_id}/{file.filename}"
    
    minio_client.put_object(
        "logs",
        object_name,
        io.BytesIO(file_data),
        length=len(file_data)
    )
    
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO sessions (session_id, ticket_id, filename, status, created_at)
            VALUES ($1, $2, $3, 'queued', NOW())
        """, session_id, ticket_id, file.filename)
    
    # Parse time range if provided
    parsed_time_start = None
    parsed_time_end = None

    if time_start:
        try:
            # Handle different input formats
            if ' ' not in time_start:  # Date only
                parsed_time_start = datetime.strptime(time_start, '%Y-%m-%d')
            elif time_start.count(':') == 1:  # Date and time without seconds
                parsed_time_start = datetime.strptime(time_start, '%Y-%m-%d %H:%M')
            else:  # Date and time with seconds
                parsed_time_start = datetime.strptime(time_start, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            print(f"Invalid time_start format: {time_start}")

    if time_end:
        try:
            # Handle different input formats
            if ' ' not in time_end:  # Date only
                parsed_time_end = datetime.strptime(time_end, '%Y-%m-%d')
                # Set to end of day
                parsed_time_end = parsed_time_end.replace(hour=23, minute=59, second=59)
            elif time_end.count(':') == 1:  # Date and time without seconds
                parsed_time_end = datetime.strptime(time_end, '%Y-%m-%d %H:%M')
            else:  # Date and time with seconds
                parsed_time_end = datetime.strptime(time_end, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            print(f"Invalid time_end format: {time_end}")

    job_data = {
        "session_id": session_id,
        "object_name": object_name,
        "filename": file.filename,
        "time_range": {
            "start": parsed_time_start.isoformat() if parsed_time_start else None,
            "end": parsed_time_end.isoformat() if parsed_time_end else None
        },
        "ticket_id": ticket_id
    }

    
    redis_client.lpush("parse_queue", json.dumps(job_data))
    
    return {
        "session_id": session_id,
        "status": "queued",
        "message": "File uploaded successfully"
    }

@app.get("/api/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    """Get session processing status"""
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow("""
            SELECT * FROM sessions WHERE session_id = $1
        """, session_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return dict(result)

@app.get("/api/sessions/{session_id}/data")
async def get_bandwidth_data(session_id: str):
    """Get bandwidth data for a session"""
    async with db_pool.acquire() as conn:
        # For large datasets, sample the data to improve chart performance
        total_count = await conn.fetchval("""
            SELECT COUNT(*) FROM bandwidth_metrics WHERE session_id = $1
        """, session_id)

        if total_count > 10000:
            # Sample every nth row to get approximately 5000 points
            sample_rate = max(1, total_count // 5000)
            rows = await conn.fetch("""
                SELECT time, modem_id, bandwidth_mbps, packet_loss_percent,
                       upstream_delay_ms, shortest_rtt_ms, smooth_rtt_ms, min_rtt_ms
                FROM (
                    SELECT *, ROW_NUMBER() OVER (ORDER BY time, modem_id) as rn
                    FROM bandwidth_metrics
                    WHERE session_id = $1
                ) sampled
                WHERE rn % $2 = 1
                ORDER BY time, modem_id
            """, session_id, sample_rate)
        else:
            rows = await conn.fetch("""
                SELECT time, modem_id, bandwidth_mbps, packet_loss_percent,
                       upstream_delay_ms, shortest_rtt_ms, smooth_rtt_ms, min_rtt_ms
                FROM bandwidth_metrics
                WHERE session_id = $1
                ORDER BY time, modem_id
            """, session_id)

        data = []
        for row in rows:
            data.append({
                "time": row["time"].isoformat(),
                "modem_id": row["modem_id"],
                "bandwidth_mbps": float(row["bandwidth_mbps"]) if row["bandwidth_mbps"] else 0,
                "packet_loss_percent": float(row["packet_loss_percent"]) if row["packet_loss_percent"] else 0,
                "upstream_delay_ms": row["upstream_delay_ms"],
                "shortest_rtt_ms": row["shortest_rtt_ms"],
                "smooth_rtt_ms": row["smooth_rtt_ms"],
                "min_rtt_ms": row["min_rtt_ms"]
            })

        # Overall session statistics
        overall_stats = await conn.fetchrow("""
            SELECT
                COUNT(DISTINCT modem_id) as modem_count,
                COUNT(*) as total_measurements,
                AVG(bandwidth_mbps) as avg_bandwidth,
                MAX(bandwidth_mbps) as max_bandwidth,
                MIN(bandwidth_mbps) as min_bandwidth,
                SUM(bandwidth_mbps) as total_bandwidth,
                AVG(packet_loss_percent) as avg_packet_loss,
                MAX(packet_loss_percent) as max_packet_loss,
                AVG(smooth_rtt_ms) as avg_rtt,
                MIN(smooth_rtt_ms) as min_rtt,
                MAX(smooth_rtt_ms) as max_rtt,
                MIN(time) as session_start,
                MAX(time) as session_end
            FROM bandwidth_metrics
            WHERE session_id = $1
        """, session_id)

        # Per-modem statistics
        modem_stats = await conn.fetch("""
            SELECT
                modem_id,
                COUNT(*) as measurement_count,
                AVG(bandwidth_mbps) as avg_bandwidth,
                MAX(bandwidth_mbps) as max_bandwidth,
                MIN(bandwidth_mbps) as min_bandwidth,
                AVG(packet_loss_percent) as avg_packet_loss,
                MAX(packet_loss_percent) as max_packet_loss,
                AVG(smooth_rtt_ms) as avg_rtt,
                MIN(smooth_rtt_ms) as min_rtt,
                MAX(smooth_rtt_ms) as max_rtt
            FROM bandwidth_metrics
            WHERE session_id = $1
            GROUP BY modem_id
            ORDER BY modem_id
        """, session_id)

        # Session quality insights
        quality_stats = await conn.fetchrow("""
            SELECT
                COUNT(CASE WHEN packet_loss_percent > 5 THEN 1 END) as high_loss_samples,
                COUNT(CASE WHEN smooth_rtt_ms > 200 THEN 1 END) as high_latency_samples,
                COUNT(CASE WHEN bandwidth_mbps < 0.5 THEN 1 END) as low_bandwidth_samples,
                AVG(CASE WHEN packet_loss_percent = 0 THEN bandwidth_mbps END) as avg_bandwidth_no_loss
            FROM bandwidth_metrics
            WHERE session_id = $1
        """, session_id)

        # Get session info
        session_info = await conn.fetchrow("""
            SELECT ticket_id, filename, created_at, status
            FROM sessions
            WHERE session_id = $1
        """, session_id)

        # Calculate session duration
        session_duration = None
        if overall_stats and overall_stats["session_start"] and overall_stats["session_end"]:
            duration = overall_stats["session_end"] - overall_stats["session_start"]
            session_duration = duration.total_seconds()

        return {
            "data": data,
            "session_id": session_id,
            "session_info": dict(session_info) if session_info else None,
            "analytics": {
                "overall_statistics": {
                    **dict(overall_stats),
                    "session_duration_seconds": session_duration,
                    "session_start": overall_stats["session_start"].isoformat() if overall_stats["session_start"] else None,
                    "session_end": overall_stats["session_end"].isoformat() if overall_stats["session_end"] else None,
                },
                "per_modem_statistics": [dict(stat) for stat in modem_stats],
                "quality_insights": {
                    **dict(quality_stats),
                    "total_samples": overall_stats["total_measurements"] if overall_stats else 0,
                    "reliability_score": (
                        100 - (float(quality_stats["high_loss_samples"] or 0) / max(overall_stats["total_measurements"], 1) * 100)
                        if overall_stats and quality_stats else 0
                    )
                }
            }
        }

@app.post("/api/merge-logs")
async def merge_logs_endpoint(
    file: UploadFile,
    start_datetime: Optional[str] = Form(None),
    end_datetime: Optional[str] = Form(None)
):
    """Merge all messages.log files from uploaded archive into chronological order"""
    if not file.filename.endswith(('.tar.bz2', '.bz2', '.tar')):
        raise HTTPException(status_code=400, detail="Invalid file format. Expected .tar.bz2, .bz2, or .tar")

    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        # Process the logs with date range filtering
        result = merge_messages_logs(temp_file_path, start_datetime, end_datetime)

        # Clean up temp file
        os.unlink(temp_file_path)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return {
            "success": True,
            "filename": file.filename,
            "metadata": result["metadata"],
            "content_length": len(result["content"])
        }

    except Exception as e:
        # Clean up temp file if it exists
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        print(f"Error processing logs: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing logs: {str(e)}")

@app.post("/api/merge-logs/download")
async def download_merged_logs(
    file: UploadFile,
    start_datetime: Optional[str] = Form(None),
    end_datetime: Optional[str] = Form(None)
):
    """Download merged messages.log files as plain text"""
    if not file.filename.endswith(('.tar.bz2', '.bz2', '.tar')):
        raise HTTPException(status_code=400, detail="Invalid file format. Expected .tar.bz2, .bz2, or .tar")

    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        # Process the logs with date range filtering
        result = merge_messages_logs(temp_file_path, start_datetime, end_datetime)

        # Clean up temp file
        os.unlink(temp_file_path)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        # Return as downloadable text file
        filename = f"merged_messages_{file.filename.replace('.tar.bz2', '').replace('.bz2', '').replace('.tar', '')}.txt"

        return PlainTextResponse(
            content=result["content"],
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "text/plain; charset=utf-8"
            }
        )

    except Exception as e:
        # Clean up temp file if it exists
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        print(f"Error downloading merged logs: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing logs: {str(e)}")