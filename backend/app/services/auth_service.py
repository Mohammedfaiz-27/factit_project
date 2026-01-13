from typing import Dict, Optional, Tuple
from app.repository.user_repository import UserRepository
from app.services.password_service import PasswordService
from app.services.token_service import TokenService
from app.models.user import UserSignupRequest, UserLoginRequest, UserResponse
from datetime import datetime
from pymongo.errors import DuplicateKeyError


class AuthService:
    """Service for authentication operations (signup, login, token refresh)"""

    def __init__(self, user_repo: UserRepository, token_service: TokenService):
        """
        Initialize the authentication service

        Args:
            user_repo: User repository instance
            token_service: Token service instance
        """
        self.user_repo = user_repo
        self.token_service = token_service
        self.password_service = PasswordService()

    def signup(self, request: UserSignupRequest) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Register a new user

        Args:
            request: User signup request data

        Returns:
            Tuple of (success, user_data_with_tokens, error_message)
        """
        # Check if email already exists
        if self.user_repo.email_exists(request.email):
            return False, None, "Email already registered"

        try:
            # Hash the password
            password_hash = self.password_service.hash_password(request.password)

            # Create user in database
            user_doc = self.user_repo.create_user(
                name=request.name,
                email=request.email,
                password_hash=password_hash
            )

            # Generate tokens
            user_id = str(user_doc["_id"])
            access_token = self.token_service.create_access_token(user_id, request.email)
            refresh_token = self.token_service.create_refresh_token(user_id, request.email)

            # Prepare response
            user_response = UserResponse(
                id=user_id,
                name=user_doc["name"],
                email=user_doc["email"],
                created_at=user_doc["created_at"]
            )

            response_data = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user": user_response.model_dump()
            }

            return True, response_data, None

        except DuplicateKeyError:
            return False, None, "Email already registered"
        except Exception as e:
            return False, None, f"Signup failed: {str(e)}"

    def login(self, request: UserLoginRequest) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Authenticate a user and generate tokens

        Args:
            request: User login request data

        Returns:
            Tuple of (success, user_data_with_tokens, error_message)
        """
        # Find user by email
        user_doc = self.user_repo.find_by_email(request.email)
        if not user_doc:
            return False, None, "Invalid email or password"

        # Verify password
        if not self.password_service.verify_password(request.password, user_doc["password_hash"]):
            return False, None, "Invalid email or password"

        # Generate tokens
        user_id = str(user_doc["_id"])
        access_token = self.token_service.create_access_token(user_id, user_doc["email"])
        refresh_token = self.token_service.create_refresh_token(user_id, user_doc["email"])

        # Prepare response
        user_response = UserResponse(
            id=user_id,
            name=user_doc["name"],
            email=user_doc["email"],
            created_at=user_doc["created_at"]
        )

        response_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user_response.model_dump()
        }

        return True, response_data, None

    def refresh_access_token(self, refresh_token: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Generate a new access token using a refresh token

        Args:
            refresh_token: Valid refresh token

        Returns:
            Tuple of (success, token_data, error_message)
        """
        # Verify refresh token
        payload = self.token_service.verify_refresh_token(refresh_token)
        if not payload:
            return False, None, "Invalid or expired refresh token"

        # Get user from database
        user_id = payload["user_id"]
        user_doc = self.user_repo.find_by_id(user_id)
        if not user_doc:
            return False, None, "User not found"

        # Generate new access token
        new_access_token = self.token_service.create_access_token(user_id, user_doc["email"])

        response_data = {
            "access_token": new_access_token,
            "token_type": "bearer"
        }

        return True, response_data, None

    def verify_token(self, access_token: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Verify an access token and return user data

        Args:
            access_token: JWT access token

        Returns:
            Tuple of (success, user_data, error_message)
        """
        # Verify token
        payload = self.token_service.verify_access_token(access_token)
        if not payload:
            return False, None, "Invalid or expired token"

        # Get user from database
        user_id = payload["user_id"]
        user_doc = self.user_repo.find_by_id(user_id)
        if not user_doc:
            return False, None, "User not found"

        # Prepare user response
        user_response = UserResponse(
            id=user_id,
            name=user_doc["name"],
            email=user_doc["email"],
            created_at=user_doc["created_at"]
        )

        return True, user_response.model_dump(), None
