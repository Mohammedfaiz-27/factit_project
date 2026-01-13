"""
Test script for the new ClaimStructuringService schema.
This demonstrates how the service transforms various user inputs.
"""

from app.services.claim_structuring_service import ClaimStructuringService
import json

def test_claim_structuring():
    """Test the new structured prompt converter with various inputs."""

    service = ClaimStructuringService()

    test_cases = [
        "did elon talk about tesla launching robotaxi next year?",
        "The Earth is flat",
        "Biden won the 2020 election",
        "COVID-19 vaccines are effective",
        "Does coffee cause cancer?",
        "Apple released iPhone 15 in September 2023",
        "The moon landing was fake"
    ]

    print("=" * 80)
    print("TESTING STRUCTURED PROMPT CONVERTER")
    print("=" * 80)
    print()

    for i, claim_text in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"TEST CASE {i}")
        print(f"{'='*80}")
        print(f"INPUT: {claim_text}")
        print(f"{'-'*80}")

        try:
            result = service.structure_claim(claim_text)
            print("OUTPUT:")
            print(json.dumps(result, indent=2))

            # Also test search query generation
            search_query = service.create_search_query(result)
            print(f"\nGENERATED SEARCH QUERY: {search_query}")

        except Exception as e:
            print(f"ERROR: {str(e)}")

    print(f"\n{'='*80}")
    print("TESTING COMPLETE")
    print(f"{'='*80}")

if __name__ == "__main__":
    test_claim_structuring()
