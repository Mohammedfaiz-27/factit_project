"""
Test Mount Everest claim with fresh research (no cache).
"""

from app.services.professional_fact_check_service import ProfessionalFactCheckService
import sys
import codecs

# Set UTF-8 encoding for console output
if sys.stdout.encoding != 'utf-8':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

def test_mount_everest_fresh():
    """Test Mount Everest claim through complete pipeline."""

    service = ProfessionalFactCheckService()

    claim = "Is Mount Everest the tallest mountain on Earth"

    print("=" * 80)
    print("TESTING: Mount Everest Claim (FRESH - NO CACHE)")
    print("=" * 80)
    print(f"\nClaim: {claim}\n")
    print("-" * 80)

    try:
        result = service.check_fact(claim)

        # Print results
        print("\n📊 STATUS:", result.get("status", "Unknown"))
        print("\n💡 EXPLANATION:")
        print(result.get("explanation", "No explanation"))

        print("\n🔬 RESEARCH SUMMARY:")
        research = result.get("research_summary", "No research")
        print(research)

        print("\n📋 KEY FINDINGS:")
        for i, finding in enumerate(result.get("findings", []), 1):
            print(f"  {i}. {finding}")

        print("\n📚 SOURCES:")
        for i, source in enumerate(result.get("sources", []), 1):
            print(f"  {i}. {source}")

        print("\n" + "=" * 80)

        # Check results
        if result.get("cached"):
            print("❌ UNEXPECTED: Result was cached (should be fresh)")
            return False
        else:
            print("✅ CONFIRMED: Fresh research performed")

        # Check for fallback
        if "Unable to perform deep research" in research or "requires Perplexity API key" in research:
            print("❌ FAILED: Perplexity API did not work")
            return False
        else:
            print("✅ SUCCESS: Perplexity API worked correctly")
            return True

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_mount_everest_fresh()
    print("\n" + "=" * 80)
    print("TEST RESULT:", "✅ PASSED" if success else "❌ FAILED")
    print("=" * 80)
    exit(0 if success else 1)
