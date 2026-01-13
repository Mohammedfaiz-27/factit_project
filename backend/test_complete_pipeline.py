"""
Test the complete fact-checking pipeline with the new structured schema.
This demonstrates end-to-end functionality with retry logic and error handling.
"""

from app.services.professional_fact_check_service import ProfessionalFactCheckService
import json
import sys
import codecs

# Set UTF-8 encoding for console output
if sys.stdout.encoding != 'utf-8':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

def test_complete_pipeline():
    """Test the full fact-checking pipeline."""

    service = ProfessionalFactCheckService()

    test_claims = [
        "did elon talk about tesla launching robotaxi next year?",
        "The Earth is flat",
        "Biden won the 2020 election"
    ]

    print("=" * 80)
    print("TESTING COMPLETE FACT-CHECKING PIPELINE")
    print("=" * 80)
    print()
    print("Features:")
    print("- Structured prompt conversion (questions -> statements)")
    print("- Entity extraction")
    print("- Perplexity research integration")
    print("- Retry logic with exponential backoff for API overload")
    print("- Database caching")
    print()

    for i, claim_text in enumerate(test_claims, 1):
        print(f"\n{'='*80}")
        print(f"TEST CASE {i}")
        print(f"{'='*80}")
        print(f"INPUT: {claim_text}")
        print(f"{'-'*80}")

        try:
            result = service.check_fact(claim_text)

            print("\nRESULT:")
            print(json.dumps(result, indent=2, ensure_ascii=False))

            # Highlight key features
            if "structured_claim" in result:
                print(f"\n{'-'*80}")
                print("STRUCTURED ANALYSIS:")
                sc = result["structured_claim"]
                print(f"  Reformulated Claim: {sc.get('claim', 'N/A')}")
                print(f"  Entities: {', '.join(sc.get('entities', [])) or 'None'}")
                print(f"  Time Period: {sc.get('time_period', 'Not specified')}")
                print(f"  Context: {sc.get('context', 'None') or 'None'}")

            if result.get("cached"):
                print(f"\n✓ CACHE HIT: This claim was retrieved from previous research")

        except Exception as e:
            print(f"\nERROR: {str(e)}")

    print(f"\n{'='*80}")
    print("TESTING COMPLETE")
    print(f"{'='*80}")

if __name__ == "__main__":
    test_complete_pipeline()
