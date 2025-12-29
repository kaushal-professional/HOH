"""
Authentication and Authorization utilities.
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db


# HTTP Bearer token security
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password_in_db: str) -> bool:
    """
    Verify plain password against stored bcrypt hash in database.

    Args:
        plain_password: Plain text password from frontend
        hashed_password_in_db: Bcrypt hash stored in database

    Returns:
        True if password matches hash, False otherwise
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password_in_db.encode('utf-8')
    )


def get_password_hash(plain_password: str) -> str:
    """
    Hash a plain password using Bcrypt.

    Bcrypt Algorithm Details:
    - Uses Blowfish cipher
    - Includes salt (automatically generated and stored in hash)
    - Cost factor (rounds): 12 by default (2^12 = 4096 iterations)
    - Format: $2b$[cost]$[22 character salt][31 character hash]

    Args:
        plain_password: Plain text password to hash

    Returns:
        Bcrypt hash of the password
    """
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    JWT Algorithm: HS256 (HMAC with SHA-256)
    - Symmetric encryption using a secret key
    - Payload is JSON-encoded and base64url-encoded
    - Signature is created using: HMACSHA256(base64UrlEncode(header) + "." + base64UrlEncode(payload), secret)
    
    Args:
        data: Dictionary containing token data (user_id, username, etc.)
        expires_delta: Optional expiration time delta
        
    Returns:
        JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Dictionary with decoded token data

    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )

        return payload

    except JWTError:
        raise credentials_exception
