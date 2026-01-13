"""
Clear cached results that contain fallback/error messages.
"""

from app.core.database import db

def clear_bad_cache():
    """Remove cached results with Perplexity fallback messages."""

    print("=" * 80)
    print("CLEARING BAD CACHED RESULTS")
    print("=" * 80)
    print()

    claims_collection = db["claims"]

    # Find all claims
    all_claims = list(claims_collection.find())
    print(f"[INFO] Total cached claims: {len(all_claims)}")
    print()

    # Find claims with fallback messages
    bad_claims = []
    for claim in all_claims:
        research_data = claim.get("research_data", {})
        summary = research_data.get("summary", "")

        if "Unable to perform deep research" in summary or "requires Perplexity API key" in summary:
            bad_claims.append(claim)
            print(f"[FOUND] Bad cache: {claim.get('prompt', '')[:60]}...")

    print()
    print(f"[INFO] Found {len(bad_claims)} bad cached results")

    if bad_claims:
        print()
        response = input("Delete these cached results? (yes/no): ").strip().lower()

        if response == 'yes':
            for claim in bad_claims:
                claims_collection.delete_one({"_id": claim["_id"]})
            print(f"\n[SUCCESS] Deleted {len(bad_claims)} bad cached results")
        else:
            print("\n[CANCELLED] No changes made")
    else:
        print("\n[INFO] No bad cached results found!")

    print()
    remaining = claims_collection.count_documents({})
    print(f"[INFO] Remaining cached claims: {remaining}")

if __name__ == "__main__":
    clear_bad_cache()
