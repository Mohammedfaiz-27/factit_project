import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional
import secrets


class TokenService:
    """Service for creating and validating JWT tokens"""

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """
        Initialize the token service

        Args:
            secret_key: Secret key for JWT signing
            algorithm: JWT algorithm (default: HS256)
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 30

    def create_access_token(self, user_id: str, email: str) -> str:
        """
        Create an access token for a user

        Args:
            user_id: User's ID
            email: User's email

        Returns:
            JWT access token
        """
        payload = {
            "user_id": user_id,
            "email": email,
            "type": "access",
            "exp": datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str, email: str) -> str:
        """
        Create a refresh token for a user

        Args:
            user_id: User's ID
            email: User's email

        Returns:
            JWT refresh token
        """
        payload = {
            "user_id": user_id,
            "email": email,
            "type": "refresh",
            "exp": datetime.utcnow() + timedelta(days=self.refresh_token_expire_days),
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(32)  # Unique token ID for revocation
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_access_token(self, token: str) -> Optional[Dict]:
        """
        Verify and decode an access token

        Args:
            token: JWT access token

        Returns:
            Decoded payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != "access":
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def verify_refresh_token(self, token: str) -> Optional[Dict]:
        """
        Verify and decode a refresh token

        Args:
            token: JWT refresh token

        Returns:
            Decoded payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != "refresh":
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def decode_token(self, token: str) -> Optional[Dict]:
        """
        Decode a token without verification (for debugging)

        Args:
            token: JWT token

        Returns:
            Decoded payload
        """
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception:
            return None
