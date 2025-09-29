from fastapi import FastAPI, UploadFile, HTTPException, Form, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncpg
import redis
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
import os
from minio import Minio
import io
import tempfile
try:
    from .log_merger import merge_messages_logs
    from .auth import (
        UserCreate, UserUpdate, UserResponse, LoginRequest, Token,
        authenticate_user, create_access_token, create_user_session,
        get_current_active_user_factory, require_admin_role_factory, get_all_users,
        create_user, update_user, delete_user, reset_user_password,
        ACCESS_TOKEN_EXPIRE_MINUTES, cleanup_expired_sessions
    )
except ImportError:
    from log_merger import merge_messages_logs
    from auth import (
        UserCreate, UserUpdate, UserResponse, LoginRequest, Token,
        authenticate_user, create_access_token, create_user_session,
        get_current_active_user_factory, require_admin_role_factory, get_all_users,
        create_user, update_user, delete_user, reset_user_password,
        ACCESS_TOKEN_EXPIRE_MINUTES, cleanup_expired_sessions
    )

app = FastAPI(title="NGL - Next Gen LULA API")

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
get_current_active_user = None
require_admin_role = None

# Dependency functions that work at runtime
async def get_auth_dependency(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    if db_pool is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Import auth functions locally to avoid circular imports
    try:
        from .auth import get_current_user_factory
    except ImportError:
        from auth import get_current_user_factory
    get_current_user = get_current_user_factory(db_pool)
    current_user = await get_current_user(credentials)

    if not current_user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_admin_dependency(current_user = Depends(get_auth_dependency)):
    if current_user["role"] != "administrator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Administrator role required."
        )
    return current_user

@app.on_event("startup")
async def startup():
    global db_pool, get_current_active_user, require_admin_role
    db_pool = await asyncpg.create_pool(
        os.getenv("DATABASE_URL"),
        min_size=5,
        max_size=20
    )

    # Initialize auth dependencies with db_pool
    get_current_active_user = get_current_active_user_factory(db_pool)
    require_admin_role = require_admin_role_factory(db_pool)

    if not minio_client.bucket_exists("logs"):
        minio_client.make_bucket("logs")

@app.get("/")
async def root():
    return {"message": "NGL - Next Gen LULA API", "version": "1.0.0"}

# Authentication endpoints
@app.post("/api/auth/login", response_model=Token)
async def login(request: Request, login_data: LoginRequest):
    """Authenticate user and return access token."""
    user = await authenticate_user(db_pool, login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create session
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")
    session_token = await create_user_session(db_pool, str(user["user_id"]), client_ip, user_agent)

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )

    user_response = UserResponse(
        user_id=str(user["user_id"]),
        username=user["username"],
        email=user["email"],
        role=user["role"],
        is_active=user["is_active"],
        created_at=user["created_at"],
        last_login=user["last_login"]
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user_response
    )

@app.post("/api/auth/logout")
async def logout(current_user=Depends(get_auth_dependency)):
    """Logout current user."""
    # In a real implementation, you might want to blacklist the JWT token
    # For now, we'll just return success
    return {"message": "Successfully logged out"}

# User management endpoints (admin only)
@app.get("/api/users", response_model=List[UserResponse])
async def get_users(
    include_inactive: bool = False,
    current_user=Depends(get_admin_dependency)
):
    """Get all users (admin only)."""
    users = await get_all_users(db_pool, include_inactive)
    return [
        UserResponse(
            user_id=str(user["user_id"]),
            username=user["username"],
            email=user["email"],
            role=user["role"],
            is_active=user["is_active"],
            created_at=user["created_at"],
            last_login=user["last_login"]
        )
        for user in users
    ]

@app.post("/api/users", response_model=UserResponse)
async def create_new_user(
    user_data: UserCreate,
    current_user=Depends(get_admin_dependency)
):
    """Create a new user (admin only)."""
    user = await create_user(db_pool, user_data, str(current_user["user_id"]))
    return UserResponse(
        user_id=str(user["user_id"]),
        username=user["username"],
        email=user["email"],
        role=user["role"],
        is_active=user["is_active"],
        created_at=user["created_at"],
        last_login=user["last_login"]
    )

@app.put("/api/users/{user_id}", response_model=UserResponse)
async def update_existing_user(
    user_id: str,
    user_data: UserUpdate,
    current_user=Depends(get_admin_dependency)
):
    """Update a user (admin only)."""
    user = await update_user(db_pool, user_id, user_data)
    return UserResponse(
        user_id=str(user["user_id"]),
        username=user["username"],
        email=user["email"],
        role=user["role"],
        is_active=user["is_active"],
        created_at=user["created_at"],
        last_login=user["last_login"]
    )

@app.delete("/api/users/{user_id}")
async def delete_existing_user(
    user_id: str,
    current_user=Depends(get_admin_dependency)
):
    """Delete (deactivate) a user (admin only)."""
    user = await delete_user(db_pool, user_id)
    return {"message": f"User {user['username']} has been deactivated"}

@app.post("/api/users/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    new_password: str = Form(...),
    current_user=Depends(get_admin_dependency)
):
    """Reset user password (admin only)."""
    user = await reset_user_password(db_pool, user_id, new_password)
    return {"message": f"Password reset for user {user['username']}"}

@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user=Depends(get_auth_dependency)):
    """Get current user information."""
    return UserResponse(
        user_id=str(current_user["user_id"]),
        username=current_user["username"],
        email=current_user["email"],
        role=current_user["role"],
        is_active=current_user["is_active"],
        created_at=current_user["created_at"],
        last_login=current_user["last_login"]
    )

@app.post("/api/upload")
async def upload_log(
    file: UploadFile,
    ticket_id: Optional[str] = Form(None),
    time_start: Optional[str] = Form(None),
    time_end: Optional[str] = Form(None),
    current_user=Depends(get_auth_dependency)
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
async def get_session_status(session_id: str, current_user=Depends(get_auth_dependency)):
    """Get session processing status"""
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow("""
            SELECT * FROM sessions WHERE session_id = $1
        """, session_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return dict(result)

@app.get("/api/sessions/{session_id}/data")
async def get_bandwidth_data(session_id: str, current_user=Depends(get_auth_dependency)):
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

        # Overall session statistics with aggregated bandwidth calculations
        # Round to nearest second to properly aggregate concurrent modem measurements
        overall_stats = await conn.fetchrow("""
            WITH aggregated_bandwidth AS (
                SELECT
                    date_trunc('second', time) as rounded_time,
                    SUM(bandwidth_mbps) as total_bandwidth_at_time,
                    AVG(packet_loss_percent) as avg_packet_loss_at_time,
                    AVG(smooth_rtt_ms) as avg_rtt_at_time
                FROM bandwidth_metrics
                WHERE session_id = $1
                GROUP BY date_trunc('second', time)
            )
            SELECT
                (SELECT COUNT(DISTINCT modem_id) FROM bandwidth_metrics WHERE session_id = $1) as modem_count,
                (SELECT COUNT(*) FROM bandwidth_metrics WHERE session_id = $1) as total_measurements,
                AVG(total_bandwidth_at_time) as avg_bandwidth,
                MAX(total_bandwidth_at_time) as max_bandwidth,
                MIN(total_bandwidth_at_time) as min_bandwidth,
                AVG(avg_packet_loss_at_time) as avg_packet_loss,
                AVG(avg_rtt_at_time) as avg_rtt,
                (SELECT MIN(time) FROM bandwidth_metrics WHERE session_id = $1) as session_start,
                (SELECT MAX(time) FROM bandwidth_metrics WHERE session_id = $1) as session_end
            FROM aggregated_bandwidth
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
    end_datetime: Optional[str] = Form(None),
    current_user=Depends(get_auth_dependency)
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
    end_datetime: Optional[str] = Form(None),
    current_user=Depends(get_auth_dependency)
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

@app.post("/api/logs/stream-download")
async def stream_download_merged_logs(
    file: UploadFile,
    start_datetime: Optional[str] = Form(None),
    end_datetime: Optional[str] = Form(None),
    current_user=Depends(get_auth_dependency)
):
    """Stream download merged messages.log files for better performance with large files"""
    if not file.filename.endswith(('.tar.bz2', '.bz2', '.tar')):
        raise HTTPException(status_code=400, detail="Invalid file format. Expected .tar.bz2, .bz2, or .tar")

    async def generate_content():
        temp_file_path = None
        try:
            # Save uploaded file to temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name

            # Process the logs with date range filtering
            result = merge_messages_logs(temp_file_path, start_datetime, end_datetime)

            if not result["success"]:
                yield f"Error: {result['error']}"
                return

            # Stream content in chunks to avoid memory issues
            content = result["content"]
            chunk_size = 8192  # 8KB chunks

            for i in range(0, len(content), chunk_size):
                yield content[i:i + chunk_size]

        except Exception as e:
            yield f"Error processing logs: {str(e)}"
        finally:
            # Clean up temp file
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    filename = f"merged_messages_{file.filename.replace('.tar.bz2', '').replace('.bz2', '').replace('.tar', '')}.txt"

    return StreamingResponse(
        generate_content(),
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        }
    )

@app.post("/api/logs/chunked-content")
async def get_chunked_log_content(
    file: UploadFile,
    start_datetime: Optional[str] = Form(None),
    end_datetime: Optional[str] = Form(None),
    page: int = Form(1),
    lines_per_page: int = Form(1000),
    current_user=Depends(get_auth_dependency)
):
    """Get log content in chunks/pages for better browser performance"""
    if not file.filename.endswith(('.tar.bz2', '.bz2', '.tar')):
        raise HTTPException(status_code=400, detail="Invalid file format. Expected .tar.bz2, .bz2, or .tar")

    temp_file_path = None
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        # Process the logs with date range filtering
        result = merge_messages_logs(temp_file_path, start_datetime, end_datetime)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        # Split content into lines
        lines = result["content"].split('\n')
        total_lines = len(lines)

        # Calculate pagination
        start_index = (page - 1) * lines_per_page
        end_index = min(start_index + lines_per_page, total_lines)

        # Get chunk of lines
        chunk_lines = lines[start_index:end_index]

        return {
            "content": '\n'.join(chunk_lines),
            "page": page,
            "lines_per_page": lines_per_page,
            "total_lines": total_lines,
            "total_pages": (total_lines + lines_per_page - 1) // lines_per_page,
            "start_line": start_index + 1,
            "end_line": end_index,
            "metadata": result.get("metadata", {})
        }

    except Exception as e:
        print(f"Error getting chunked log content: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing logs: {str(e)}")
    finally:
        # Clean up temp file
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

@app.post("/api/analyze-sessions")
async def analyze_session_file(
    file: UploadFile,
    start_datetime: str = Form(None),
    end_datetime: str = Form(None),
    current_user=Depends(get_auth_dependency)
):
    """Analyze log file for session information and streaming details"""
    if not file.filename.endswith(('.tar.bz2', '.bz2', '.tar', '.log', '.txt')):
        raise HTTPException(status_code=400, detail="Invalid file format. Expected .tar.bz2, .bz2, .tar, .log, or .txt")

    temp_file_path = None
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        # Import and use session analyzer
        try:
            from .session_analyzer import SessionAnalyzer
        except ImportError:
            from session_analyzer import SessionAnalyzer

        analyzer = SessionAnalyzer()
        result = analyzer.analyze_file(temp_file_path, start_datetime, end_datetime)

        return result

    except Exception as e:
        print(f"Error analyzing session file: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error analyzing session file: {str(e)}")
    finally:
        # Clean up temp file
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)