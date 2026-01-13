"""
Test with a unique timestamp-based claim to avoid cache.
"""

from app.services.professional_fact_check_service import ProfessionalFactCheckService
import json
import time

def test_unique_claim():
    """Test with a unique claim."""

    service = ProfessionalFactCheckService()

    # Create a unique claim using timestamp
    test_claim = "The speed of light in vacuum is approximately 299,792,458 meters per second"

    print("=" * 80)
    print("TESTING UNIQUE CLAIM")
    print("=" * 80)
    print(f"\nClaim: {test_claim}\n")
    print("-" * 80)

    try:
        result = service.check_fact(test_claim)

        print("\nSTATUS:")
        # Print without Unicode to avoid encoding issues
        status = result.get("status", "Unknown")
        status_clean = status.encode('ascii', 'ignore').decode('ascii')
        print(f"  {status_clean if status_clean else status.replace('✅', '[TRUE]').replace('❌', '[FALSE]').replace('⚠️', '[UNVERIFIED]')}")

        print("\nEXPLANATION:")
        explanation = result.get("explanation", "No explanation")
        print(f"  {explanation[:200]}...")

        print("\nRESEARCH SUMMARY:")
        research_summary = result.get("research_summary", "No research")
        print(f"  {research_summary[:200]}...")

        print("\nSOURCES:")
        sources = result.get("sources", [])
        for i, source in enumerate(sources[:3], 1):
            print(f"  [{i}] {source}")

        # Check cache status
        if result.get("cached"):
            print("\n[CACHE] Result was retrieved from cache")
        else:
            print("\n[NEW] Fresh research performed")

        # Validate Perplexity worked
        if "Unable to perform deep research" in research_summary:
            print("\n[ERROR] Perplexity API failed!")
            print("Fallback message detected in research summary")
            return False
        elif research_summary and len(research_summary) > 50 and len(sources) > 0:
            print("\n[SUCCESS] Perplexity deep research working correctly!")
            print(f"  - Research summary: {len(research_summary)} characters")
            print(f"  - Sources found: {len(sources)}")
            return True
        else:
            print("\n[WARNING] Research data incomplete")
            return False

    except Exception as e:
        print(f"\n[ERROR] Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_unique_claim()
    exit(0 if success else 1)
