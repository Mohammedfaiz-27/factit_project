from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional

from app.services.token_service import TokenService
from app.core.config import JWT_SECRET_KEY, JWT_ALGORITHM

# Initialize token service
token_service = TokenService(JWT_SECRET_KEY, JWT_ALGORITHM)

# Security scheme
security = HTTPBearer()


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """
    Middleware to verify JWT token and extract user information

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        Token payload with user_id and email

    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials
    payload = token_service.verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return payload


async def get_current_user_id(token_payload: Dict = Depends(verify_token)) -> str:
    """
    Extract user ID from verified token

    Args:
        token_payload: Verified token payload

    Returns:
        User ID
    """
    return token_payload["user_id"]


async def get_current_user_email(token_payload: Dict = Depends(verify_token)) -> str:
    """
    Extract user email from verified token

    Args:
        token_payload: Verified token payload

    Returns:
        User email
    """
    return token_payload["email"]


# Optional: For routes that work with or without authentication
async def optional_verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[Dict]:
    """
    Optional authentication - doesn't raise error if no token provided

    Args:
        credentials: Optional bearer token

    Returns:
        Token payload if valid, None if no token or invalid
    """
    if not credentials:
        return None

    token = credentials.credentials
    return token_service.verify_access_token(token)
