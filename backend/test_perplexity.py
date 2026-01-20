"""
Debug Perplexity response parsing.
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('PERPLEXITY_API_KEY')

url = "https://api.perplexity.ai/chat/completions"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Use the EXACT same prompt as the service
research_prompt = """
You are a professional fact-checker. Research the following claim using only credible sources (Reuters, BBC, AP News, PTI, The Hindu, Times of India, NDTV, India Today, official government portals, PIB India, scientific journals).

Claim: Tamil Nadu government provides free textbooks to school students

Additional Details:
- Key Entities: Tamil Nadu, government, school students
- Time Period: Not specified
- Context: None provided

Search Query: Tamil Nadu government provides free textbooks to school students

Provide:
1. A summary of verified information from credible sources
2. Key findings (3-5 bullet points)
3. List of credible sources used (with URLs when available)

Format your response as:
SUMMARY: [brief summary]
FINDINGS:
- [finding 1]
- [finding 2]
- [finding 3]
SOURCES:
- [source 1]
- [source 2]
"""

payload = {
    "model": "sonar-pro",
    "messages": [
        {
            "role": "system",
            "content": "You are a professional fact-checking assistant with access to real-time information. Cite credible sources including international (Reuters, BBC, AP) and regional sources (PTI, The Hindu, Times of India, government portals)."
        },
        {
            "role": "user",
            "content": research_prompt
        }
    ],
    "temperature": 0.2,
    "max_tokens": 2000
}

print("Calling Perplexity with service prompt...")
response = requests.post(url, headers=headers, json=payload, timeout=30)

if response.status_code == 200:
    result = response.json()
    raw_text = result['choices'][0]['message']['content']

    print("\n" + "=" * 60)
    print("RAW RESPONSE FROM PERPLEXITY:")
    print("=" * 60)
    print(raw_text)
    print("=" * 60)

    # Check if expected format exists
    print("\nFormat check:")
    print(f"  Has 'SUMMARY:' = {'SUMMARY:' in raw_text}")
    print(f"  Has 'FINDINGS:' = {'FINDINGS:' in raw_text}")
    print(f"  Has 'SOURCES:' = {'SOURCES:' in raw_text}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
