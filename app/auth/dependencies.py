"""Authentication dependencies for FastAPI routes."""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.requests import Request
from sqlalchemy.orm import Session

from app.auth import auth_service
from app.auth.database import User, get_db


async def get_current_user_dependency(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency to get the current authenticated user.
    Extracts JWT token from Authorization header and validates it.
    """
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    token_data = auth_service.decode_access_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = auth_service.get_user_by_id(db, token_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """
    Dependency to optionally get the current authenticated user.
    Returns None if not authenticated.
    """
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1]
    token_data = auth_service.decode_access_token(token)
    if not token_data:
        return None

    user = auth_service.get_user_by_id(db, token_data.user_id)
    return user
