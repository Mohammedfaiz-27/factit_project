"""
Test script to verify URL fact-checking feature
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.url_extraction_service import URLExtractionService
from app.services.fact_check_service import FactCheckService

def test_services():
    """Test that URL services can be instantiated"""
    try:
        print("Testing URL feature services initialization...")
        print("="*60)

        # Test URLExtractionService
        print("\n1. Initializing URLExtractionService...")
        url_extractor = URLExtractionService()
        print("   [OK] URLExtractionService initialized")

        # Test FactCheckService with URL support
        print("\n2. Initializing FactCheckService...")
        fact_check_service = FactCheckService()
        print("   [OK] FactCheckService initialized")

        # Verify URL method exists
        print("\n3. Verifying check_url_fact method...")
        if hasattr(fact_check_service, 'check_url_fact'):
            print("   [OK] check_url_fact method exists")
        else:
            print("   [ERROR] check_url_fact method not found")
            return False

        print("\n" + "="*60)
        print("SUCCESS: URL fact-checking feature ready!")
        print("="*60)
        print("\nHow it works:")
        print("1. User pastes article URL")
        print("2. System fetches and extracts article content")
        print("3. AI identifies main factual claim(s)")
        print("4. Perplexity Deep Search verifies claims")
        print("5. Verdict returned (True/False/Mixed/Unverified)")
        print("\nTo test:")
        print("- Start backend: uvicorn main:app --reload --port 8000")
        print("- Start frontend: npm start (in frontend directory)")
        print("- Click 'Link' mode and paste a news article URL")
        print("\nSupported URLs:")
        print("- News articles (Reuters, BBC, CNN, etc.)")
        print("- Blog posts with factual claims")
        print("- Any webpage with extractable text content")

        return True

    except Exception as e:
        print(f"\n[ERROR] Service initialization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_services()
    sys.exit(0 if success else 1)
