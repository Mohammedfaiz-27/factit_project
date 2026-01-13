from pymongo.collection import Collection
from typing import Optional, Dict, Any
from datetime import datetime
from bson import ObjectId


class UserRepository:
    """Repository for user data operations in MongoDB"""

    def __init__(self, collection: Collection):
        """
        Initialize the repository with a MongoDB collection

        Args:
            collection: MongoDB collection for users
        """
        self.collection = collection
        # Create unique index on email
        self.collection.create_index("email", unique=True)

    def create_user(self, name: str, email: str, password_hash: str) -> Dict[str, Any]:
        """
        Create a new user in the database

        Args:
            name: User's name
            email: User's email (must be unique)
            password_hash: Hashed password

        Returns:
            Created user document
        """
        user_doc = {
            "name": name,
            "email": email.lower(),  # Store emails in lowercase for consistency
            "password_hash": password_hash,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = self.collection.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        return user_doc

    def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Find a user by email

        Args:
            email: User's email

        Returns:
            User document if found, None otherwise
        """
        return self.collection.find_one({"email": email.lower()})

    def find_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a user by ID

        Args:
            user_id: User's ObjectId as string

        Returns:
            User document if found, None otherwise
        """
        try:
            return self.collection.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None

    def email_exists(self, email: str) -> bool:
        """
        Check if an email already exists

        Args:
            email: Email to check

        Returns:
            True if email exists, False otherwise
        """
        return self.collection.count_documents({"email": email.lower()}) > 0

    def update_password(self, user_id: str, new_password_hash: str) -> bool:
        """
        Update user's password

        Args:
            user_id: User's ObjectId as string
            new_password_hash: New hashed password

        Returns:
            True if update successful, False otherwise
        """
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "password_hash": new_password_hash,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        except Exception:
            return False

    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user

        Args:
            user_id: User's ObjectId as string

        Returns:
            True if delete successful, False otherwise
        """
        try:
            result = self.collection.delete_one({"_id": ObjectId(user_id)})
            return result.deleted_count > 0
        except Exception:
            return False
