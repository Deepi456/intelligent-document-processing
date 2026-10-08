"""Authentication API routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import models, auth_service
from app.auth.database import User, get_db
from app.auth.dependencies import get_current_user_dependency

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=models.TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: models.UserCreate,
    db: Session = Depends(get_db),
) -> dict:
    """
    Register a new user.

    - Validates email format
    - Checks password requirements (min 6 characters)
    - Verifies password confirmation matches
    - Creates user with hashed password
    - Returns JWT token on success
    """
    # Validate password confirmation
    if user_data.password != user_data.password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )

    try:
        # Create user
        user = auth_service.register_user(db, user_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Create access token
    access_token = auth_service.create_access_token(
        data={"sub": user.id, "email": user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": auth_service.create_user_response(user),
    }


@router.post("/login", response_model=models.TokenResponse)
def login(
    credentials: models.UserLogin,
    db: Session = Depends(get_db),
) -> dict:
    """
    Login with email and password.

    Returns JWT token on success, error on failure.
    """
    user = auth_service.authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth_service.create_access_token(
        data={"sub": user.id, "email": user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": auth_service.create_user_response(user),
    }


@router.get("/me", response_model=models.UserResponse)
def get_current_user(
    current_user: User = Depends(get_current_user_dependency),
) -> dict:
    """
    Get current authenticated user info.

    Uses the existing JWT bearer dependency; the response schema
    (UserResponse) never includes the password hash.
    """
    return auth_service.create_user_response(current_user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> None:
    """
    Logout the current user.

    Note: JWT is stateless, so logout is handled on the client side
    by removing the token. This endpoint is for future extensibility.
    """
    return None
