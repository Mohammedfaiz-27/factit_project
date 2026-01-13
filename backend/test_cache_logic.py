"""
Test that failed research results are NOT cached.
"""

from app.services.professional_fact_check_service import ProfessionalFactCheckService
from app.core.database import db

def test_cache_logic():
    """Verify failed results aren't cached, but successful ones are."""

    print("=" * 80)
    print("TESTING CACHE LOGIC")
    print("=" * 80)
    print()

    claims_collection = db["claims"]

    # Clear existing claims
    count_before = claims_collection.count_documents({})
    print(f"[INFO] Claims in database before test: {count_before}")

    service = ProfessionalFactCheckService()

    # Test with a new unique claim
    test_claim = "Saturn has rings made of ice and rock particles"

    print(f"\n[TEST] Checking claim: {test_claim}")
    print("-" * 80)

    result = service.check_fact(test_claim)

    # Check the database
    count_after = claims_collection.count_documents({})
    print(f"\n[INFO] Claims in database after test: {count_after}")

    # Verify caching logic
    research_summary = result.get("research_summary", "")
    is_failed = "Unable to perform deep research" in research_summary

    if is_failed:
        if count_after > count_before:
            print("\n[ERROR] Failed result was cached (should NOT be cached)")
            return False
        else:
            print("\n[SUCCESS] Failed result was NOT cached (correct behavior)")
            return True
    else:
        if count_after > count_before:
            print("\n[SUCCESS] Successful result was cached (correct behavior)")
            print(f"[INFO] Research quality: {len(research_summary)} chars, {len(result.get('sources', []))} sources")
            return True
        else:
            print("\n[ERROR] Successful result was NOT cached (should be cached)")
            return False

if __name__ == "__main__":
    success = test_cache_logic()
    print("\n" + "=" * 80)
    print("TEST RESULT:", "[PASS]" if success else "[FAIL]")
    print("=" * 80)
    exit(0 if success else 1)
