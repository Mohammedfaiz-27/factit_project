"""
Test the exact Mount Everest claim the user reported.
"""

from app.services.professional_fact_check_service import ProfessionalFactCheckService
import json

def test_mount_everest():
    """Test Mount Everest claim through complete pipeline."""

    service = ProfessionalFactCheckService()

    claim = "Is Mount Everest the tallest mountain on Earth"

    print("=" * 80)
    print("TESTING: Mount Everest Claim")
    print("=" * 80)
    print(f"\nClaim: {claim}\n")
    print("-" * 80)

    try:
        result = service.check_fact(claim)

        # Print results without Unicode emojis
        print("\nSTATUS:", result.get("status", "Unknown").replace("✅", "[TRUE]").replace("❌", "[FALSE]").replace("⚠️", "[UNVERIFIED]"))
        print("\nEXPLANATION:")
        print(result.get("explanation", "No explanation"))

        print("\nRESEARCH SUMMARY:")
        research = result.get("research_summary", "No research")
        print(research)

        print("\nFINDINGS:")
        for finding in result.get("findings", []):
            print(f"  - {finding}")

        print("\nSOURCES:")
        for source in result.get("sources", []):
            print(f"  - {source}")

        # Check if cached
        if result.get("cached"):
            print("\n[NOTE] This was a cached result")
        else:
            print("\n[NOTE] This was fresh research")

        # Check for fallback
        if "Unable to perform deep research" in research:
            print("\n[ERROR] PERPLEXITY API FAILED - FALLBACK DETECTED")
            return False
        else:
            print("\n[SUCCESS] Perplexity API worked correctly")
            return True

    except Exception as e:
        print(f"\n[ERROR] Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_mount_everest()
    exit(0 if success else 1)
