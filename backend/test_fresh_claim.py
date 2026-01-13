"""
Test a fresh claim (not cached) to verify Perplexity integration in complete pipeline.
"""

from app.services.professional_fact_check_service import ProfessionalFactCheckService
import json

def test_fresh_claim():
    """Test with a claim that shouldn't be cached."""

    service = ProfessionalFactCheckService()

    # Use a unique timestamp-based claim to avoid cache
    import time
    timestamp = int(time.time())
    test_claim = f"Python is a programming language created by Guido van Rossum"

    print("=" * 80)
    print("TESTING FRESH CLAIM (NO CACHE)")
    print("=" * 80)
    print(f"\nClaim: {test_claim}\n")
    print("-" * 80)

    try:
        result = service.check_fact(test_claim)

        print("\nRESULT:")
        print(json.dumps(result, indent=2, ensure_ascii=True))

        # Check if research was performed
        if result.get("cached"):
            print("\n[INFO] Result was cached")
        else:
            print("\n[INFO] Fresh research performed")

        # Check research quality
        research_summary = result.get("research_summary", "")
        if "Unable to perform deep research" in research_summary:
            print("[ERROR] Perplexity API failed - fallback used")
        elif research_summary and len(research_summary) > 50:
            print("[SUCCESS] Perplexity deep research completed successfully!")
        else:
            print("[WARNING] Research data seems incomplete")

    except Exception as e:
        print(f"\n[ERROR] {str(e)}")

if __name__ == "__main__":
    test_fresh_claim()
