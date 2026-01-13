from ..core.database import claims_collection
from datetime import datetime
import uuid
import hashlib


class ClaimRepository:
    def __init__(self):
        self.collection = claims_collection

    def find_cached_claim(self, claim_text: str):
        """
        Check if an exact claim already exists in the database.
        Uses a hash for efficient lookup.

        Args:
            claim_text (str): The claim to search for

        Returns:
            dict or None: Cached claim data if found, None otherwise
        """
        claim_hash = self._hash_claim(claim_text)

        try:
            cached = self.collection.find_one({"claim_hash": claim_hash})
            if cached:
                print(f"Cache hit for claim: {claim_text[:50]}...")
            return cached
        except Exception as e:
            print(f"Error checking cache: {str(e)}")
            return None

    def save(self, claim_text: str, response_text: str, structured_data: dict = None, research_data: dict = None):
        """
        Save the claim, response, and research data into MongoDB.

        Args:
            claim_text (str): Original claim
            response_text (str): Formatted fact-check result
            structured_data (dict): Structured claim data
            research_data (dict): Perplexity research results
        """
        claim_hash = self._hash_claim(claim_text)

        claim_doc = {
            "_id": str(uuid.uuid4()),
            "claim_hash": claim_hash,
            "prompt": claim_text,
            "response": response_text,
            "structured_data": structured_data or {},
            "research_data": research_data or {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        try:
            self.collection.insert_one(claim_doc)
            print(f"Saved claim to database: {claim_text[:50]}...")
            return claim_doc["_id"]
        except Exception as e:
            print(f"Error saving claim: {str(e)}")
            return None

    def _hash_claim(self, claim_text: str) -> str:
        """
        Create a hash of the claim for efficient lookup.
        Normalizes the text before hashing.

        Args:
            claim_text (str): Claim to hash

        Returns:
            str: SHA256 hash of normalized claim
        """
        # Normalize: lowercase, strip whitespace, remove extra spaces
        normalized = " ".join(claim_text.lower().strip().split())
        return hashlib.sha256(normalized.encode()).hexdigest()

    def get_by_id(self, claim_id: str):
        """Get claim by ID."""
        return self.collection.find_one({"_id": claim_id})

    def get_all(self):
        """Get all claims."""
        return list(self.collection.find())

    def get_recent_claims(self, limit: int = 10):
        """
        Get recent claims, sorted by creation date.

        Args:
            limit (int): Number of recent claims to retrieve

        Returns:
            list: Recent claims
        """
        try:
            return list(self.collection.find().sort("created_at", -1).limit(limit))
        except Exception as e:
            print(f"Error retrieving recent claims: {str(e)}")
            return []
