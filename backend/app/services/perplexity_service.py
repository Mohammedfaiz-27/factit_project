from app.core.config import PERPLEXITY_API_KEY
import requests
import json

class PerplexityService:
    """
    Integrates with Perplexity AI for deep research and fact verification.
    """

    def __init__(self):
        if not PERPLEXITY_API_KEY:
            print("WARNING: PERPLEXITY_API_KEY not set. Research functionality will be limited.")
            self.api_key = None
        else:
            self.api_key = PERPLEXITY_API_KEY

        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.model = "sonar-pro"  # Perplexity's online research model

    def deep_research(self, search_query: str, structured_claim: dict) -> dict:
        """
        Perform deep research using Perplexity AI.

        Args:
            search_query (str): Optimized search query
            structured_claim (dict): Structured claim data

        Returns:
            dict: Research results with findings and sources
        """
        if not self.api_key:
            return self._fallback_research(search_query)

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Extract components from new schema
            claim = structured_claim.get('claim', search_query)
            entities = structured_claim.get('entities', [])
            context = structured_claim.get('context', '')
            time_period = structured_claim.get('time_period', '')

            # Format entities for display
            entities_text = ', '.join(entities) if entities else 'N/A'

            research_prompt = f"""
You are a professional fact-checker. Research the following claim using only credible sources (Reuters, BBC, AP News, official government portals, scientific journals).

Claim: {claim}

Additional Details:
- Key Entities: {entities_text}
- Time Period: {time_period if time_period else 'Not specified'}
- Context: {context if context else 'None provided'}

Search Query: {search_query}

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
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional fact-checking assistant with access to real-time information. Only cite credible sources."
                    },
                    {
                        "role": "user",
                        "content": research_prompt
                    }
                ],
                "temperature": 0.2,  # Lower temperature for more factual responses
                "max_tokens": 2000
            }

            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                research_text = result['choices'][0]['message']['content']

                # Parse the response
                parsed_result = self._parse_research_response(research_text)
                return parsed_result
            else:
                print(f"Perplexity API error: {response.status_code} - {response.text}")
                return self._fallback_research(search_query)

        except requests.exceptions.Timeout:
            print("Perplexity API timeout")
            return self._fallback_research(search_query)
        except Exception as e:
            print(f"Perplexity research error: {str(e)}")
            return self._fallback_research(search_query)

    def _parse_research_response(self, research_text: str) -> dict:
        """
        Parse the research response from Perplexity.

        Args:
            research_text (str): Raw research text

        Returns:
            dict: Parsed research with summary, findings, sources
        """
        summary = ""
        findings = []
        sources = []

        # Split into sections
        lines = research_text.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()

            if line.startswith("SUMMARY:"):
                current_section = "summary"
                summary = line.replace("SUMMARY:", "").strip()
            elif line.startswith("FINDINGS:"):
                current_section = "findings"
            elif line.startswith("SOURCES:"):
                current_section = "sources"
            elif line.startswith("-") or line.startswith("•"):
                content = line.lstrip("-•").strip()
                if current_section == "findings" and content:
                    findings.append(content)
                elif current_section == "sources" and content:
                    sources.append(content)
            elif current_section == "summary" and line:
                summary += " " + line

        return {
            "summary": summary.strip(),
            "findings": findings,
            "sources": sources
        }

    def _fallback_research(self, search_query: str) -> dict:
        """
        Fallback research when Perplexity API is unavailable.

        Args:
            search_query (str): Search query

        Returns:
            dict: Basic research structure
        """
        return {
            "summary": f"Unable to perform deep research for: {search_query}. Perplexity API not configured.",
            "findings": [
                "Deep research requires Perplexity API key",
                "Please configure PERPLEXITY_API_KEY in your .env file"
            ],
            "sources": []
        }
