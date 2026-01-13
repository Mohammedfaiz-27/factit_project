"""
Debug API key loading to find the actual issue.
"""

import os
from dotenv import load_dotenv

print("=" * 80)
print("DEBUGGING API KEY LOADING")
print("=" * 80)
print()

# Test 1: Load .env explicitly
print("[TEST 1] Loading .env file...")
load_dotenv()

# Test 2: Check if key exists in environment
perplexity_key = os.getenv("PERPLEXITY_API_KEY")
print(f"[TEST 2] PERPLEXITY_API_KEY from os.getenv: {perplexity_key[:15] if perplexity_key else 'NOT FOUND'}...")

# Test 3: Import from config
print("[TEST 3] Importing from app.core.config...")
from app.core.config import PERPLEXITY_API_KEY
print(f"  PERPLEXITY_API_KEY: {PERPLEXITY_API_KEY[:15] if PERPLEXITY_API_KEY else 'NOT FOUND'}...")

# Test 4: Check PerplexityService
print("[TEST 4] Checking PerplexityService...")
from app.services.perplexity_service import PerplexityService
service = PerplexityService()
print(f"  service.api_key: {service.api_key[:15] if service.api_key else 'NOT FOUND'}...")

# Test 5: Try actual API call
print()
print("[TEST 5] Attempting actual Perplexity API call...")
structured_claim = {
    "claim": "Mount Everest is the tallest mountain on Earth",
    "entities": ["Mount Everest"],
    "time_period": "",
    "context": ""
}
search_query = "Mount Everest tallest mountain"

result = service.deep_research(search_query, structured_claim)

print()
print("API CALL RESULT:")
if "Unable to perform deep research" in result.get("summary", ""):
    print("[ERROR] Fallback message detected - API call failed!")
    print(f"  Summary: {result.get('summary', '')}")
else:
    print("[SUCCESS] API call succeeded!")
    print(f"  Summary length: {len(result.get('summary', ''))} chars")
    print(f"  Findings: {len(result.get('findings', []))} items")
    print(f"  Sources: {len(result.get('sources', []))} items")
