"""
Test Perplexity API connection and functionality.
"""

from app.services.perplexity_service import PerplexityService
from app.services.claim_structuring_service import ClaimStructuringService
import json

def test_perplexity():
    """Test if Perplexity API is working."""

    print("=" * 80)
    print("TESTING PERPLEXITY API")
    print("=" * 80)
    print()

    # Initialize services
    perplexity = PerplexityService()
    structuring = ClaimStructuringService()

    # Check if API key is loaded
    if perplexity.api_key:
        print(f"[OK] API Key loaded: {perplexity.api_key[:10]}...")
        print(f"[OK] Using model: {perplexity.model}")
    else:
        print("[ERROR] No API key found!")
        return

    print()

    # Test with a simple claim
    test_claim = "The Earth is flat"
    print(f"Testing claim: {test_claim}")
    print("-" * 80)

    # Structure the claim
    structured = structuring.structure_claim(test_claim)
    search_query = structuring.create_search_query(structured)

    print(f"Search query: {search_query}")
    print()

    # Try deep research
    print("Calling Perplexity API...")
    result = perplexity.deep_research(search_query, structured)

    print()
    print("RESULT:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()

    # Check if it's a fallback
    if "Unable to perform deep research" in result.get("summary", ""):
        print("[ERROR] Perplexity API call failed - using fallback")
    else:
        print("[SUCCESS] Perplexity API call successful!")

if __name__ == "__main__":
    test_perplexity()
