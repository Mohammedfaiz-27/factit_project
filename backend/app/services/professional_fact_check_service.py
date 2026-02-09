from app.repository.claim_repository import ClaimRepository
from app.core.config import GEMINI_API_KEY, GEMINI_MODEL
from app.services.claim_structuring_service import ClaimStructuringService
from app.services.perplexity_service import PerplexityService
from app.services.x_analysis_service import XAnalysisService
from google import genai
from datetime import datetime
import time
import concurrent.futures


class ProfessionalFactCheckService:
    """
    Professional fact-checking service following the 6-step pipeline:
    1. Check Database Cache
    2. LLM Structuring
    3. Perplexity Deep Research + X Analysis (parallel)
    4. Generate Final Result
    5. Database Storage
    6. Return Response

    X Analysis runs in parallel with Perplexity and provides supplementary
    context from external links found in X posts. X is never a source of truth.
    """

    def __init__(self):
        self.repo = ClaimRepository()
        self.structuring = ClaimStructuringService()
        self.perplexity = PerplexityService()
        self.x_analysis = XAnalysisService()

        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL

    def check_fact(self, claim_text: str) -> dict:
        """
        Execute the complete professional fact-checking pipeline.

        Args:
            claim_text (str): The claim to fact-check

        Returns:
            dict: Formatted fact-check result
        """
        # Step 1: Check Database Cache
        cached_claim = self.repo.find_cached_claim(claim_text)
        if cached_claim:
            return self._format_cached_response(cached_claim)

        # Step 2: LLM Structuring
        structured_claim = self.structuring.structure_claim(claim_text)
        search_query = self.structuring.create_search_query(structured_claim)

        # Step 3: Perplexity Deep Research + X Analysis (parallel execution)
        research_data, x_analysis_data = self._run_parallel_research(
            search_query, structured_claim
        )

        # Step 4: Generate Final Result (with combined research context)
        final_result = self._generate_verdict(
            claim_text, structured_claim, research_data, x_analysis_data
        )

        # Step 5: Database Storage
        formatted_response = self._format_response(claim_text, final_result, research_data, structured_claim, x_analysis_data)

        # Only cache if research was successful (don't cache API failures)
        research_summary = research_data.get("summary", "")
        is_successful_research = (
            research_summary and
            "Unable to perform deep research" not in research_summary and
            "requires Perplexity API key" not in research_summary
        )

        if is_successful_research:
            self.repo.save(
                claim_text=claim_text,
                response_text=str(formatted_response),
                structured_data=structured_claim,
                research_data=research_data
            )
        else:
            print(f"[WARNING] Skipping cache for failed research: {claim_text[:50]}...")

        # Step 6: Return Response
        formatted_response["cached"] = False
        return formatted_response

    def _run_parallel_research(self, search_query: str, structured_claim: dict) -> tuple:
        """
        Run Perplexity Deep Research and X Analysis in parallel.

        Args:
            search_query (str): Optimized search query
            structured_claim (dict): Structured claim data

        Returns:
            tuple: (research_data, x_analysis_data)
        """
        research_data = None
        x_analysis_data = None

        print(f"\n[RESEARCH] Starting parallel research phase...")
        print(f"[RESEARCH] - Perplexity Deep Search: Starting")
        print(f"[RESEARCH] - X Analysis: Starting")

        # Use ThreadPoolExecutor for parallel execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both tasks
            perplexity_future = executor.submit(
                self.perplexity.deep_research, search_query, structured_claim
            )
            x_analysis_future = executor.submit(
                self.x_analysis.analyze_claim, structured_claim, search_query
            )

            # Wait for Perplexity (primary - required)
            try:
                research_data = perplexity_future.result(timeout=60)
                print(f"[RESEARCH] - Perplexity Deep Search: Complete")
            except Exception as e:
                print(f"[RESEARCH] - Perplexity Deep Search: Failed ({str(e)})")
                research_data = {
                    "summary": f"Research failed: {str(e)}",
                    "findings": [],
                    "sources": []
                }

            # Wait for X Analysis (supplementary - optional)
            try:
                x_analysis_data = x_analysis_future.result(timeout=30)
                posts_analyzed = x_analysis_data.get("posts_analyzed", 0)
                sources_found = len(x_analysis_data.get("external_sources", []))
                print(f"[RESEARCH] - X Analysis: Complete ({posts_analyzed} posts, {sources_found} external sources)")
            except Exception as e:
                print(f"[RESEARCH] - X Analysis: Failed ({str(e)})")
                x_analysis_data = {
                    "has_relevant_posts": False,
                    "posts_analyzed": 0,
                    "external_sources": [],
                    "discussion_summary": "",
                    "analysis_note": f"X analysis unavailable: {str(e)}",
                    "error": str(e)
                }

        print(f"[RESEARCH] Parallel research phase complete\n")

        return research_data, x_analysis_data

    def _generate_verdict(self, claim_text: str, structured_claim: dict, research_data: dict, x_analysis_data: dict = None, max_retries: int = 3) -> dict:
        """
        Generate the final verdict based on research data and X analysis.

        Args:
            claim_text (str): Original claim
            structured_claim (dict): Structured claim data with new schema
            research_data (dict): Perplexity research results
            x_analysis_data (dict): X analysis results with external sources (optional)
            max_retries (int): Maximum retry attempts for API overload

        Returns:
            dict: Verdict with status and explanation
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                chat = self.client.chats.create(model=self.model)

                # Extract structured components
                structured_statement = structured_claim.get("claim", claim_text)
                entities = structured_claim.get("entities", [])
                time_period = structured_claim.get("time_period", "")
                context = structured_claim.get("context", "")

                # Build context from Perplexity research (PRIMARY)
                research_summary = research_data.get("summary", "No research data available")
                findings = research_data.get("findings", [])
                sources = research_data.get("sources", [])

                findings_text = "\n".join([f"- {f}" for f in findings]) if findings else "No specific findings"
                sources_text = "\n".join([f"- {s}" for s in sources]) if sources else "No sources available"
                entities_text = ", ".join(entities) if entities else "N/A"

                # Build X analysis context (SUPPLEMENTARY)
                x_context = self._build_x_analysis_context(x_analysis_data)

                # Build structured context section
                structured_context = f"""
STRUCTURED CLAIM ANALYSIS:
- Main Claim: {structured_statement}
- Key Entities: {entities_text}
- Time Period: {time_period if time_period else "Not specified"}
- Context: {context if context else "None provided"}
"""

                verdict_prompt = f"""
You are a professional fact-checker. Based on the research data below, evaluate the truthfulness of this claim.

ORIGINAL INPUT: "{claim_text}"

{structured_context}

===============================================================================
PRIMARY RESEARCH (Perplexity Deep Search) - EVIDENCE WEIGHT: HIGH
===============================================================================
RESEARCH SUMMARY:
{research_summary}

KEY FINDINGS:
{findings_text}

CREDIBLE SOURCES:
{sources_text}

===============================================================================
SUPPLEMENTARY CONTEXT (X-Linked External Sources) - EVIDENCE WEIGHT: LOW
===============================================================================
{x_context}

===============================================================================
EVIDENCE WEIGHTING RULES:
===============================================================================
1. Perplexity Deep Search is your PRIMARY evidence source - give it highest weight
2. X-linked external sources may REINFORCE or SUPPLEMENT Perplexity findings
3. IGNORE X analysis completely if it provides no credible external links
4. NEVER use engagement metrics (likes, retweets, views) as evidence of truth
5. NEVER treat social media popularity or virality as proof of accuracy

Determine the verdict based on these STRICT criteria:

✅ TRUE - ONLY use when:
- Credible sources explicitly CONFIRM the claim with direct evidence
- Example: Claim "X won election" → Sources report "X won election" = TRUE

❌ FALSE - ONLY use when:
- Credible sources explicitly CONTRADICT the claim with direct evidence
- There must be POSITIVE EVIDENCE that the opposite is true
- Example: Claim "X won election" → Sources report "Y won election" = FALSE
- NEVER mark as FALSE just because "no sources found" or "no coverage exists"

⚠️ UNVERIFIED - Use for ALL of these situations:
- No credible sources cover the topic at all
- Sources discuss related topics but don't confirm or deny the specific claim
- "No reports found" or "unable to verify" = UNVERIFIED (not FALSE)
- Local events not covered by major media = UNVERIFIED (not FALSE)
- Only partial information available = UNVERIFIED

CRITICAL RULES:
1. "No sources confirm X" does NOT mean X is false - it means UNVERIFIED
2. "No reports found about X" = UNVERIFIED, never FALSE
3. To mark FALSE, you MUST have evidence proving the OPPOSITE is true
4. When in doubt, choose UNVERIFIED over FALSE

Provide:
1. STATUS: One of [✅ True, ❌ False, ⚠️ Unverified]
2. EXPLANATION: A brief (2-3 sentences), factual explanation based on the research

Format your response EXACTLY as:
STATUS: [status]
EXPLANATION: [explanation]
"""

                response = chat.send_message(verdict_prompt)
                result_text = response.text.strip()

                # Parse the response
                status = "⚠️ Unverified"
                explanation = "Unable to verify this claim based on available information."

                lines = result_text.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith("STATUS:"):
                        status = line.replace("STATUS:", "").strip()
                    elif line.startswith("EXPLANATION:"):
                        # Get explanation (might span multiple lines)
                        explanation = line.replace("EXPLANATION:", "").strip()
                        # Check if explanation continues on next lines
                        for j in range(i + 1, len(lines)):
                            if not lines[j].startswith("STATUS:") and lines[j].strip():
                                explanation += " " + lines[j].strip()
                            else:
                                break

                return {
                    "status": status,
                    "explanation": explanation.strip(),
                    "sources": sources
                }

            except Exception as e:
                last_error = e
                error_msg = str(e)

                # Check if it's a 503 (overload) error
                if "503" in error_msg or "UNAVAILABLE" in error_msg or "overload" in error_msg.lower():
                    if attempt < max_retries - 1:
                        # Exponential backoff: wait 2^attempt seconds
                        wait_time = 2 ** attempt
                        print(f"Gemini API overloaded during verdict generation (attempt {attempt + 1}/{max_retries}). Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"Gemini API overloaded after {max_retries} attempts.")
                else:
                    print(f"Verdict generation error: {error_msg}")

                # If last attempt, return error result
                if attempt == max_retries - 1:
                    return {
                        "status": "⚠️ Unverified",
                        "explanation": f"Unable to generate verdict. {error_msg}",
                        "sources": research_data.get("sources", [])
                    }

        # Fallback if all retries failed
        return {
            "status": "⚠️ Unverified",
            "explanation": f"Unable to generate verdict after {max_retries} attempts. Please try again later.",
            "sources": research_data.get("sources", [])
        }

    def _build_x_analysis_context(self, x_analysis_data: dict) -> str:
        """
        Build the X analysis context section for the verdict prompt.

        Args:
            x_analysis_data (dict): X analysis results

        Returns:
            str: Formatted X analysis context for the prompt
        """
        if not x_analysis_data:
            return "X analysis was not performed."

        # Get analysis note (summary of what was found)
        analysis_note = x_analysis_data.get("analysis_note", "No X analysis available.")

        # Check if there's an error
        if x_analysis_data.get("error"):
            return f"X analysis unavailable: {x_analysis_data.get('error')}"

        # Check if no relevant posts were found
        if not x_analysis_data.get("has_relevant_posts", False):
            return analysis_note

        # Build external sources section
        external_sources = x_analysis_data.get("external_sources", [])
        discussion_summary = x_analysis_data.get("discussion_summary", "")

        context_parts = [analysis_note, ""]

        if discussion_summary:
            context_parts.append(f"Discussion Context: {discussion_summary}")
            context_parts.append("")

        if external_sources:
            context_parts.append("External Sources Found via X:")
            for source in external_sources:
                domain = source.get("domain", "unknown")
                url = source.get("url", "")
                title = source.get("title", "")
                tier = source.get("credibility_tier", "unknown")

                if title:
                    context_parts.append(f"- [{tier.upper()}] {domain}: {title}")
                else:
                    context_parts.append(f"- [{tier.upper()}] {domain}: {url[:80]}...")
        else:
            context_parts.append("External Sources Found via X: None")

        return "\n".join(context_parts)

    def _format_response(self, claim_text: str, verdict: dict, research_data: dict, structured_claim: dict = None, x_analysis_data: dict = None) -> dict:
        """
        Format the final response in a clean, human-readable style.

        Args:
            claim_text (str): Original claim
            verdict (dict): Verdict data
            research_data (dict): Research data
            structured_claim (dict): Structured claim data (optional)
            x_analysis_data (dict): X analysis results (optional)

        Returns:
            dict: Formatted response
        """
        response = {
            "claim_text": claim_text,
            "status": verdict.get("status", "⚠️ Unverified"),
            "explanation": verdict.get("explanation", "No explanation available"),
            "sources": verdict.get("sources", []),
            "research_summary": research_data.get("summary", ""),
            "findings": research_data.get("findings", [])
        }

        # Include structured claim data if available
        if structured_claim:
            response["structured_claim"] = {
                "claim": structured_claim.get("claim", claim_text),
                "entities": structured_claim.get("entities", []),
                "time_period": structured_claim.get("time_period", ""),
                "context": structured_claim.get("context", "")
            }

        # Include X analysis data if available
        if x_analysis_data:
            external_sources = x_analysis_data.get("external_sources", [])
            response["x_analysis"] = {
                "posts_analyzed": x_analysis_data.get("posts_analyzed", 0),
                "external_sources_found": len(external_sources),
                "sources": [
                    {"url": s.get("url", ""), "domain": s.get("domain", ""), "credibility_tier": s.get("credibility_tier", "unknown")}
                    for s in external_sources
                ],
                "discussion_summary": x_analysis_data.get("discussion_summary", ""),
                "note": x_analysis_data.get("analysis_note", "")
            }

        return response

    def _format_cached_response(self, cached_claim: dict) -> dict:
        """
        Format a cached claim response.

        Args:
            cached_claim (dict): Cached claim from database

        Returns:
            dict: Formatted cached response
        """
        # Try to parse structured response if available
        response = cached_claim.get("response", "")

        # If response is already structured (dict stored as string), parse it
        if isinstance(response, str) and response.startswith("{"):
            try:
                import json
                response_dict = json.loads(response.replace("'", '"'))
                response_dict["cached"] = True
                response_dict["cache_note"] = "✓ Retrieved from previous research"
                return response_dict
            except:
                pass

        # Fallback: return basic structure
        return {
            "claim_text": cached_claim.get("prompt", ""),
            "status": "⚠️ Cached Result",
            "explanation": str(response),
            "sources": cached_claim.get("research_data", {}).get("sources", []),
            "cached": True,
            "cache_note": "✓ Retrieved from previous research"
        }
