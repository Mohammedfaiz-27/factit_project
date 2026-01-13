from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any

from app.models.user import (
    UserSignupRequest,
    UserLoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse
)
from app.services.auth_service import AuthService
from app.services.token_service import TokenService
from app.repository.user_repository import UserRepository
from app.core.database import users_collection
from app.core.config import JWT_SECRET_KEY, JWT_ALGORITHM

# Initialize services
user_repository = UserRepository(users_collection)
token_service = TokenService(JWT_SECRET_KEY, JWT_ALGORITHM)
auth_service = AuthService(user_repository, token_service)

# Create router
router = APIRouter()

# Security scheme for protected routes
security = HTTPBearer()


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: UserSignupRequest):
    """
    Register a new user

    Args:
        request: User signup data (name, email, password)

    Returns:
        Access token, refresh token, and user data

    Raises:
        HTTPException: If email already exists or signup fails
    """
    success, data, error = auth_service.signup(request)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )

    return data


@router.post("/login", response_model=TokenResponse)
async def login(request: UserLoginRequest):
    """
    Authenticate a user

    Args:
        request: User login credentials (email, password)

    Returns:
        Access token, refresh token, and user data

    Raises:
        HTTPException: If credentials are invalid
    """
    success, data, error = auth_service.login(request)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error
        )

    return data


@router.post("/refresh")
async def refresh_token(request: RefreshTokenRequest):
    """
    Refresh access token using refresh token

    Args:
        request: Refresh token

    Returns:
        New access token

    Raises:
        HTTPException: If refresh token is invalid or expired
    """
    success, data, error = auth_service.refresh_access_token(request.refresh_token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error
        )

    return data


@router.post("/logout")
async def logout():
    """
    Logout user (client-side token removal)

    Note: Since we're using stateless JWT, actual logout happens on client side
    by removing the tokens. This endpoint is here for API consistency.

    Returns:
        Success message
    """
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Get current authenticated user's information

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        Current user data

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    success, user_data, error = auth_service.verify_token(token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user_data


# Dependency for protected routes
async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Dependency to extract user ID from JWT token

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        User ID

    Raises:
        HTTPException: If token is invalid
    """
    token = credentials.credentials
    payload = token_service.verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return payload["user_id"]
