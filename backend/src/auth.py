from datetime import datetime, timedelta
from typing import Optional, Union
import os
import secrets
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
import asyncpg
from pydantic import BaseModel

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
SESSION_TOKEN_EXPIRE_HOURS = 24 * 7  # 7 days

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security
security = HTTPBearer()

# Models
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "regular"

class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class TokenData(BaseModel):
    username: Optional[str] = None

# Utility functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_session_token() -> str:
    """Create a secure session token."""
    return secrets.token_urlsafe(32)

# Database functions
async def get_user_by_username(db_pool, username: str):
    """Get user by username from database."""
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT user_id, username, email, password_hash, role, is_active,
                   created_at, last_login
            FROM users
            WHERE username = $1 AND is_active = TRUE
        """, username)
        return user

async def get_user_by_id(db_pool, user_id: str):
    """Get user by ID from database."""
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT user_id, username, email, password_hash, role, is_active,
                   created_at, last_login
            FROM users
            WHERE user_id = $1
        """, user_id)
        return user

async def create_user(db_pool, user_data: UserCreate, created_by: Optional[str] = None):
    """Create a new user in the database."""
    hashed_password = get_password_hash(user_data.password)

    async with db_pool.acquire() as conn:
        try:
            user = await conn.fetchrow("""
                INSERT INTO users (username, email, password_hash, role, created_by)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING user_id, username, email, role, is_active, created_at, last_login
            """, user_data.username, user_data.email, hashed_password, user_data.role, created_by)
            return user
        except asyncpg.UniqueViolationError as e:
            if "username" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already exists"
                )
            elif "email" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User already exists"
                )

async def update_user(db_pool, user_id: str, user_data: UserUpdate):
    """Update user in the database."""
    fields = []
    values = []

    if user_data.email is not None:
        fields.append("email = $" + str(len(values) + 1))
        values.append(user_data.email)

    if user_data.role is not None:
        fields.append("role = $" + str(len(values) + 1))
        values.append(user_data.role)

    if user_data.is_active is not None:
        fields.append("is_active = $" + str(len(values) + 1))
        values.append(user_data.is_active)

    fields.append("updated_at = NOW()")

    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    query = f"""
        UPDATE users
        SET {', '.join(fields)}
        WHERE user_id = ${len(values) + 1}
        RETURNING user_id, username, email, role, is_active, created_at, last_login
    """
    values.append(user_id)

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(query, *values)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user

async def delete_user(db_pool, user_id: str):
    """Delete (deactivate) user in the database."""
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("""
            UPDATE users
            SET is_active = FALSE, updated_at = NOW()
            WHERE user_id = $1
            RETURNING user_id, username
        """, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user

async def reset_user_password(db_pool, user_id: str, new_password: str):
    """Reset user password."""
    hashed_password = get_password_hash(new_password)

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("""
            UPDATE users
            SET password_hash = $2, updated_at = NOW()
            WHERE user_id = $1
            RETURNING user_id, username
        """, user_id, hashed_password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user

async def authenticate_user(db_pool, username: str, password: str):
    """Authenticate user credentials."""
    user = await get_user_by_username(db_pool, username)
    if not user:
        return False
    if not verify_password(password, user["password_hash"]):
        return False

    # Update last login
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE users SET last_login = NOW() WHERE user_id = $1
        """, user["user_id"])

    return user

async def create_user_session(db_pool, user_id: str, ip_address: str = None, user_agent: str = None):
    """Create a user session."""
    session_token = create_session_token()
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_TOKEN_EXPIRE_HOURS)

    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO user_sessions (session_token, user_id, expires_at, ip_address, user_agent)
            VALUES ($1, $2, $3, $4, $5)
        """, session_token, user_id, expires_at, ip_address, user_agent)

    return session_token

async def validate_session_token(db_pool, session_token: str):
    """Validate a session token."""
    async with db_pool.acquire() as conn:
        session = await conn.fetchrow("""
            SELECT s.user_id, s.expires_at, u.username, u.email, u.role, u.is_active
            FROM user_sessions s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.session_token = $1 AND s.expires_at > NOW() AND u.is_active = TRUE
        """, session_token)
        return session

async def delete_user_session(db_pool, session_token: str):
    """Delete a user session (logout)."""
    async with db_pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM user_sessions WHERE session_token = $1
        """, session_token)

async def cleanup_expired_sessions(db_pool):
    """Clean up expired sessions."""
    async with db_pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM user_sessions WHERE expires_at < NOW()
        """)

async def get_all_users(db_pool, include_inactive: bool = False):
    """Get all users."""
    where_clause = "" if include_inactive else "WHERE is_active = TRUE"

    async with db_pool.acquire() as conn:
        users = await conn.fetch(f"""
            SELECT user_id, username, email, role, is_active, created_at, last_login
            FROM users
            {where_clause}
            ORDER BY created_at DESC
        """)
        return users

# Dependency functions
def get_current_user_factory(db_pool):
    """Factory function to create get_current_user dependency with db_pool."""
    async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
        """Get current user from JWT token."""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            token_data = TokenData(username=username)
        except JWTError:
            raise credentials_exception

        user = await get_user_by_username(db_pool, username=token_data.username)
        if user is None:
            raise credentials_exception
        return user

    return get_current_user

def get_current_active_user_factory(db_pool):
    """Factory function to create get_current_active_user dependency."""
    get_current_user = get_current_user_factory(db_pool)

    async def get_current_active_user(current_user=Depends(get_current_user)):
        """Get current active user."""
        if not current_user["is_active"]:
            raise HTTPException(status_code=400, detail="Inactive user")
        return current_user

    return get_current_active_user

def require_admin_role_factory(db_pool):
    """Factory function to create require_admin_role dependency."""
    get_current_active_user = get_current_active_user_factory(db_pool)

    async def require_admin_role(current_user=Depends(get_current_active_user)):
        """Require admin role for access."""
        if current_user["role"] != "administrator":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions. Administrator role required."
            )
        return current_user

    return require_admin_role