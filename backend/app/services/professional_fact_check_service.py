from app.repository.claim_repository import ClaimRepository
from app.core.config import GEMINI_API_KEY, GEMINI_MODEL
from app.services.claim_structuring_service import ClaimStructuringService
from app.services.perplexity_service import PerplexityService
from app.services.x_analysis_service import XAnalysisService
from google import genai
from datetime import datetime
import time
import re
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

        print(f"[RESEARCH] Parallel research phase complete")

        # Retry with alternative query if Perplexity returned nothing useful
        if not self._assess_perplexity_relevance(research_data):
            alt_query = self.structuring.create_alternative_query(structured_claim)
            if alt_query and alt_query != search_query:
                print(f"[RESEARCH] Perplexity returned no findings. Retrying with alternative query...")
                try:
                    retry_data = self.perplexity.deep_research(alt_query, structured_claim)
                    if self._assess_perplexity_relevance(retry_data):
                        research_data = retry_data
                        print(f"[RESEARCH] Retry successful — found relevant results")
                    else:
                        print(f"[RESEARCH] Retry also returned no findings")
                except Exception as e:
                    print(f"[RESEARCH] Retry failed: {str(e)}")

        print(f"[RESEARCH] Research phase complete\n")

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

                # Determine if Perplexity returned relevant results
                perplexity_has_relevant = self._assess_perplexity_relevance(research_data)
                x_has_sources = (
                    x_analysis_data and
                    x_analysis_data.get("has_relevant_posts", False) and
                    len(x_analysis_data.get("external_sources", [])) > 0
                )

                # Dynamic evidence weighting
                x_elevation_guidance = ""
                if perplexity_has_relevant:
                    perplexity_weight = "HIGH"
                    x_weight = "LOW (supplementary)"
                elif x_has_sources:
                    # Perplexity failed but X found external sources — promote X
                    perplexity_weight = "LOW (returned irrelevant or no results)"
                    x_weight = "ELEVATED — primary evidence source for this claim (Perplexity research was inconclusive)"
                    # Count credible X sources for stronger guidance
                    credible_x_sources = [
                        s for s in x_analysis_data.get("external_sources", [])
                        if s.get("credibility_tier") in ("primary", "secondary")
                    ]
                    if credible_x_sources:
                        x_elevation_guidance = f"""
CRITICAL — X SOURCES AS PRIMARY EVIDENCE:
Primary research (Perplexity) found NO relevant results for this claim, but X analysis
found {len(credible_x_sources)} credible external source(s) from recognized news outlets.
You MUST evaluate these X-linked sources as your primary evidence:
- If these credible news articles CONFIRM the claim → mark TRUE
- Do NOT default to "Unverified" merely because Perplexity's search failed
- Media reports from reputable outlets ARE sufficient evidence for widely-reported
  government announcements, public events, and official statements
- The question is: "Do credible sources confirm this?" — not "Did Perplexity find it?"
"""
                else:
                    perplexity_weight = "LOW (returned irrelevant or no results)"
                    x_weight = "LOW (no external sources found)"

                # Build structured context section
                structured_context = f"""
STRUCTURED CLAIM ANALYSIS:
- Main Claim: {structured_statement}
- Key Entities: {entities_text}
- Time Period: {time_period if time_period else "Not specified"}
- Context: {context if context else "None provided"}
"""

                # Extract claim metadata for context-aware verdict
                claim_type = structured_claim.get("claim_type", "other")
                geographic_scope = structured_claim.get("geographic_scope", "national")
                location = structured_claim.get("location", "")
                research_limitations = research_data.get("research_limitations", "")

                # Detect press release characteristics
                press_release_info = self._detect_press_release_indicators(claim_text)
                press_release_context = ""
                if press_release_info["is_likely_press_release"]:
                    indicators_text = "\n".join([f"  - {ind}" for ind in press_release_info["indicators"]])
                    press_release_context = f"""
===============================================================================
PRESS RELEASE / OFFICIAL ANNOUNCEMENT DETECTION
===============================================================================
This claim contains {press_release_info['indicator_count']} indicators of an official government press release:
{indicators_text}

IMPORTANT CONTEXT FOR VERDICT:
- Claims with these characteristics are typically copy-pasted from official district
  administration press releases, government notifications, or collectorate announcements.
- These are distributed via official WhatsApp groups, notice boards, and local media
  BEFORE being indexed by search engines.
- The inability to find this announcement online does NOT mean it is false.
- For UNVERIFIED verdicts on press releases, your explanation MUST:
  1. Acknowledge the claim has characteristics of an official government press release
  2. Note that such announcements are often not immediately indexed online
  3. Suggest specific verification methods: check the district collectorate's official
     website/social media, or contact the phone numbers mentioned in the claim
"""

                verdict_prompt = f"""
You are a professional fact-checker with expertise across multiple domains. Evaluate the truthfulness of this claim using ALL available evidence: the research data below, X-linked external sources, AND your own verified knowledge.

ORIGINAL INPUT: "{claim_text}"

{structured_context}

CLAIM METADATA:
- Claim Type: {claim_type.replace('_', ' ').title()}
- Geographic Scope: {geographic_scope.upper()}
- Location: {location if location else "Not specified"}

===============================================================================
PRIMARY RESEARCH (Perplexity Deep Search) - EVIDENCE WEIGHT: {perplexity_weight}
===============================================================================
RESEARCH SUMMARY:
{research_summary}

KEY FINDINGS:
{findings_text}

CREDIBLE SOURCES:
{sources_text}

RESEARCH LIMITATIONS:
{research_limitations if research_limitations else "None reported"}

===============================================================================
{"X-LINKED EXTERNAL SOURCES" if not x_has_sources or perplexity_has_relevant else "X-LINKED EXTERNAL SOURCES (ELEVATED: Primary research was inconclusive)"} - EVIDENCE WEIGHT: {x_weight}
===============================================================================
{x_context}
{x_elevation_guidance}
{press_release_context}
===============================================================================
STEP 0: CLAIM CATEGORY CLASSIFICATION (do this FIRST)
===============================================================================
Classify this claim into ONE of these categories:

CATEGORY A — SPECIFIC EVENT CLAIM:
   A recent or specific event, incident, or announcement (protest, accident, arrest,
   appointment, scheme launch, speech, court ruling, election result, etc.)
   → These REQUIRE external source evidence (articles, press releases, official records)
   → Your own knowledge is NOT sufficient — events need source confirmation

CATEGORY B — ESTABLISHED KNOWLEDGE CLAIM:
   A well-documented, widely-accepted fact about culture, history, geography, economics,
   science, institutions, or education. Examples:
   - "Tamil Nadu is known for Bharatanatyam and Carnatic music"
   - "Tamil Nadu is a leading manufacturing state"
   - "The Earth revolves around the Sun"
   - "India's capital is New Delhi"
   → These can be verified using your own training knowledge from textbooks,
     encyclopedias, academic sources, and institutional records
   → These do NOT need recent news articles — they are baseline knowledge
   → If you are confident this is established knowledge, you may verify it directly

CATEGORY C — MIXED CLAIM:
   Contains both established facts and specific event details.
   → Verify each component separately

State which category this claim belongs to before proceeding.

===============================================================================
STEP 1: EVIDENCE ASSESSMENT
===============================================================================

FOR CATEGORY A (Specific Events):
   - Evaluate research findings and X-linked sources for direct evidence
   - If research returned irrelevant results (gazette docs, homepage listings, unrelated
     documents), acknowledge this and do NOT treat them as evidence
   - If X found credible external source links, treat them as valid evidence
   - Check scope match: local events may not appear in national/international media

FOR CATEGORY B (Established Knowledge):
   - You ARE authorized to verify these from your training knowledge
   - If the claim is factually accurate based on well-documented academic, cultural,
     historical, scientific, or economic knowledge, mark it TRUE
   - Cite the TYPE of authoritative sources that document this (e.g., "documented in
     NCERT textbooks, Encyclopaedia Britannica, academic literature, UNESCO records")
   - Do NOT mark established facts as "Unverified" simply because a web search
     didn't return a specific article — that is a search limitation, not factual uncertainty
   - Only mark established knowledge as FALSE if it is demonstrably wrong

FOR CATEGORY C (Mixed Claims):
   - Verify each component separately and report accordingly

===============================================================================
STEP 2: VERDICT DETERMINATION
===============================================================================

✅ TRUE - Use when:
- [Category A] Credible external sources explicitly CONFIRM the claim
- [Category B] The claim is well-established knowledge that you can verify from authoritative sources (textbooks, encyclopedias, academic literature, government records, institutional data)
- [Category C] All components are verified (some via sources, some via established knowledge)

❌ FALSE - ONLY when:
- Credible sources or established knowledge explicitly CONTRADICT the claim
- There must be POSITIVE EVIDENCE that the claim is wrong
- NEVER mark as FALSE because "no search results found"

⚠️ UNVERIFIED - Use when:
- [Category A] No relevant sources found for a specific event claim
- [Category A] Research returned off-topic results and no X sources available
- [Category B] RARELY — only if the claim is about obscure knowledge you cannot confidently verify
- Scope mismatch: local event searched only in national/international media
- Partial information: some parts confirmed, others cannot be verified

===============================================================================
STEP 3: EXPLANATION RULES
===============================================================================

FOR TRUE VERDICTS:
- [Category A] Cite the specific sources that confirm the claim
- [Category B] State: "This is established [cultural/historical/economic/scientific] knowledge documented in [source types]." Then briefly explain why it's true.

FOR UNVERIFIED VERDICTS (Category A specific events only):
- State what sources were searched and what was found
- Recommend specific source types for verification
- Use: "This claim could not be independently verified through the online sources accessible to this system."
- NEVER use: "No credible sources were found" or "There is no evidence to support this claim"
- For local events, note that absence of national media coverage is expected

FOR FALSE VERDICTS:
- Cite the specific evidence that contradicts the claim

CRITICAL RULES:
1. NEVER mark well-known cultural, historical, geographic, economic, or scientific facts as "Unverified" just because a web search didn't find articles. That is a SEARCH LIMITATION, not factual uncertainty.
2. "No search results" for established knowledge = search failure, NOT evidence of falsehood
3. For specific events: "no sources confirm X" = UNVERIFIED (not FALSE)
4. When in doubt between TRUE and UNVERIFIED for established knowledge, lean TRUE if you are confident
5. When in doubt between UNVERIFIED and FALSE for specific events, lean UNVERIFIED

Provide:
1. CATEGORY: [A/B/C] with brief justification
2. STATUS: One of [✅ True, ❌ False, ⚠️ Unverified]
3. EXPLANATION: A 2-4 sentence explanation following the rules above.
4. KEY_FINDINGS: 3-5 bullet points summarizing the most important facts discovered during verification (from research data, X sources, AND/OR your own verified knowledge). These should be specific factual statements, not vague summaries.
5. VERIFIED_SOURCES: List the specific sources that support your verdict. For Category A, cite the news articles or official sources. For Category B, cite authoritative reference types (e.g., "ISRO official mission page", "NCERT textbooks", "WHO guidelines"). Always provide source names — never leave this empty.

Format your response EXACTLY as:
CATEGORY: [A/B/C] - [brief justification]
STATUS: [status]
EXPLANATION: [explanation]
KEY_FINDINGS:
- [finding 1]
- [finding 2]
- [finding 3]
VERIFIED_SOURCES:
- [source 1]
- [source 2]
"""

                response = chat.send_message(verdict_prompt)
                result_text = response.text.strip()

                # Parse the response
                status = "⚠️ Unverified"
                explanation = "Unable to verify this claim based on available information."
                category = ""
                gemini_findings = []
                gemini_sources = []

                lines = result_text.split('\n')
                current_section = None
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith("CATEGORY:"):
                        current_section = "category"
                        category = stripped.replace("CATEGORY:", "").strip()
                    elif stripped.startswith("STATUS:"):
                        current_section = "status"
                        status = stripped.replace("STATUS:", "").strip()
                    elif stripped.startswith("EXPLANATION:"):
                        current_section = "explanation"
                        explanation = stripped.replace("EXPLANATION:", "").strip()
                    elif stripped.startswith("KEY_FINDINGS:"):
                        current_section = "findings"
                    elif stripped.startswith("VERIFIED_SOURCES:"):
                        current_section = "sources"
                    elif stripped.startswith("-") or stripped.startswith("•"):
                        content = stripped.lstrip("-•").strip()
                        if current_section == "findings" and content:
                            gemini_findings.append(content)
                        elif current_section == "sources" and content:
                            gemini_sources.append(content)
                    elif current_section == "explanation" and stripped:
                        # Explanation can span multiple lines
                        explanation += " " + stripped

                if category:
                    print(f"[Verdict] Claim category: {category}")
                    print(f"[Verdict] Gemini findings: {len(gemini_findings)}, Gemini sources: {len(gemini_sources)}")

                # Use Perplexity sources if available, otherwise use Gemini's sources
                final_sources = sources if sources else gemini_sources

                return {
                    "status": status,
                    "explanation": explanation.strip(),
                    "sources": final_sources,
                    "gemini_findings": gemini_findings,
                    "gemini_sources": gemini_sources,
                    "claim_category": category
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

    def _assess_perplexity_relevance(self, research_data: dict) -> bool:
        """
        Assess whether Perplexity returned relevant results or irrelevant/empty ones.

        Returns True if Perplexity found specific, relevant evidence.
        Returns False if results are empty, off-topic, or generic.
        """
        summary = research_data.get("summary", "").lower()
        findings = research_data.get("findings", [])
        sources = research_data.get("sources", [])

        # No findings and no sources = clearly irrelevant
        if not findings and not sources:
            return False

        # Check if summary explicitly says nothing was found
        no_result_indicators = [
            "no specific articles",
            "no specific reports",
            "no credible sources",
            "were not found",
            "could not be found",
            "no relevant",
            "no coverage",
            "no direct evidence",
            "no reports about",
            "no articles about",
            "not found in the sources",
            "unrelated to",
            "none contained",
            "none addressed",
        ]

        for indicator in no_result_indicators:
            if indicator in summary:
                return False

        # If there are findings and sources and summary doesn't say "nothing found", consider relevant
        if findings and sources:
            return True

        # If there are findings but no sources, still somewhat relevant
        if findings:
            return True

        return False

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
                description = source.get("description", "")
                tier = source.get("credibility_tier", "unknown")

                if title:
                    line = f"- [{tier.upper()}] {domain}: {title}"
                    if description:
                        line += f" — {description[:150]}"
                    context_parts.append(line)
                else:
                    context_parts.append(f"- [{tier.upper()}] {domain}: {url[:80]}...")
        else:
            context_parts.append("External Sources Found via X: None")

        return "\n".join(context_parts)

    def _detect_press_release_indicators(self, claim_text: str) -> dict:
        """
        Detect if the claim text has characteristics of an official government press release.

        Press releases typically contain: phone numbers, official designations (IAS/IPS),
        specific dates with DD.MM.YYYY format, monetary amounts, office addresses,
        and specific event timings.

        Returns:
            dict with is_likely_press_release (bool), indicators (list), indicator_count (int)
        """
        indicators = []

        # Phone numbers (Indian format: 04365 250126, 9499055737, etc.)
        if re.search(r'\d{4,5}\s?\d{5,6}', claim_text):
            indicators.append("official contact phone numbers")

        # Specific time ranges (10.00 மணி, etc.)
        if re.search(r'\d{1,2}[.:]\d{2}\s*(மணி|am|pm|AM|PM)', claim_text, re.IGNORECASE):
            indicators.append("specific event timings")

        # Monetary amounts (Tamil ரூ or Rs or ₹)
        if re.search(r'ரூ[.]?\s*[\d,]+|Rs\.?\s*[\d,]+|₹\s*[\d,]+', claim_text):
            indicators.append("specific monetary amounts/stipends")

        # Government designations (IAS, IPS, Collector, etc.)
        if re.search(r'இ\.ஆ\.ப\.|I\.A\.S|IAS|IPS|ஆட்சித்தலைவர்|Collector|Commissioner|District Collector', claim_text, re.IGNORECASE):
            indicators.append("government official designations (IAS/Collector)")

        # Official address/office references
        if re.search(r'அலுவலகம்|அலுவலக|வளாகம்|நிலையம்|office|campus', claim_text, re.IGNORECASE):
            indicators.append("institutional/office addresses")

        # Formatted dates (DD.MM.YYYY)
        if re.search(r'\d{1,2}\.\d{1,2}\.\d{4}', claim_text):
            indicators.append("specific formatted dates (DD.MM.YYYY)")

        is_likely = len(indicators) >= 3

        return {
            "is_likely_press_release": is_likely,
            "indicators": indicators,
            "indicator_count": len(indicators)
        }

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
        # Use Perplexity findings/sources when available, fall back to Gemini's
        perplexity_findings = research_data.get("findings", [])
        perplexity_sources = research_data.get("sources", [])
        gemini_findings = verdict.get("gemini_findings", [])
        gemini_sources = verdict.get("gemini_sources", [])

        # Check if Perplexity actually returned relevant data
        perplexity_relevant = self._assess_perplexity_relevance(research_data)

        final_findings = perplexity_findings if (perplexity_findings and perplexity_relevant) else gemini_findings
        final_sources = perplexity_sources if (perplexity_sources and perplexity_relevant) else gemini_sources

        response = {
            "claim_text": claim_text,
            "status": verdict.get("status", "⚠️ Unverified"),
            "explanation": verdict.get("explanation", "No explanation available"),
            "sources": final_sources,
            "research_summary": research_data.get("summary", ""),
            "findings": final_findings,
            "research_limitations": research_data.get("research_limitations", "")
        }

        # Include structured claim data if available
        if structured_claim:
            response["structured_claim"] = {
                "claim": structured_claim.get("claim", claim_text),
                "claim_type": structured_claim.get("claim_type", "other"),
                "geographic_scope": structured_claim.get("geographic_scope", "national"),
                "location": structured_claim.get("location", ""),
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
