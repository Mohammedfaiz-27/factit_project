from app.repository.claim_repository import ClaimRepository
from app.core.config import GEMINI_API_KEY, GEMINI_MODEL
from app.services.claim_structuring_service import ClaimStructuringService
from app.services.perplexity_service import PerplexityService
from app.services.x_analysis_service import XAnalysisService
from app.services.news_search_service import NewsSearchService
from google import genai
from datetime import datetime
import time
import re


class ProfessionalFactCheckService:
    """
    Professional fact-checking service following the 6-step pipeline:
    1. Check Database Cache
    2. LLM Structuring
    3. Research Phase:
       a) X Analysis FIRST — extracts posts with text, date, author priority
       b) Perplexity Deep Research — receives X evidence as input leads
    4. Generate Final Result
    5. Database Storage
    6. Return Response
    """

    def __init__(self):
        self.repo = ClaimRepository()
        self.structuring = ClaimStructuringService()
        self.perplexity = PerplexityService()
        self.x_analysis = XAnalysisService()
        self.news_search = NewsSearchService()

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

        # Step 2: LLM Structuring + Classification
        structured_claim = self.structuring.structure_claim(claim_text)
        claim_category = self.structuring.classify_claim(structured_claim)
        structured_claim["claim_category"] = claim_category
        print(f"[Pipeline] Claim classified as: {claim_category}")
        search_query = self.structuring.create_search_query(structured_claim)

        # Step 3: X Analysis → Perplexity Deep Research → News Fallback (sequential)
        research_data, x_analysis_data, news_data = self._run_research(
            search_query, structured_claim
        )

        # Step 4: Generate Final Result (with combined research context)
        final_result = self._generate_verdict(
            claim_text, structured_claim, research_data, x_analysis_data, news_data=news_data
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

    def _run_research(self, search_query: str, structured_claim: dict) -> tuple:
        """
        Run X Analysis first, then feed X evidence into Perplexity Deep Research.
        If Perplexity returns no results, fall back to Google News RSS search.

        Flow:
          Step 3a: X Analysis → extracts posts with text, date, author priority
          Step 3b: Perplexity receives X posts as research leads
          Step 3c: If Perplexity fails → Google News RSS fallback

        Args:
            search_query (str): Optimized search query
            structured_claim (dict): Structured claim data

        Returns:
            tuple: (research_data, x_analysis_data, news_data)
        """
        print(f"\n[RESEARCH] Starting sequential research phase...")

        # Step 3a: Run X Analysis FIRST
        print(f"[RESEARCH] Step 3a: X Analysis — searching for posts...")
        x_analysis_data = None
        try:
            x_analysis_data = self.x_analysis.analyze_claim(structured_claim, search_query)
            posts_analyzed = x_analysis_data.get("posts_analyzed", 0)
            posts_content = x_analysis_data.get("posts_content", [])
            sources_found = len(x_analysis_data.get("external_sources", []))
            news_posts = sum(1 for p in posts_content if p.get("priority", 3) <= 2)
            print(f"[RESEARCH] Step 3a: X Analysis complete ({posts_analyzed} posts, {news_posts} from news channels, {sources_found} external links)")
        except Exception as e:
            print(f"[RESEARCH] Step 3a: X Analysis failed ({str(e)})")
            x_analysis_data = {
                "has_relevant_posts": False,
                "posts_analyzed": 0,
                "posts_content": [],
                "external_sources": [],
                "discussion_summary": "",
                "analysis_note": f"X analysis unavailable: {str(e)}",
                "error": str(e)
            }

        # Step 3b: Extract X posts as evidence for Perplexity
        # Only feed news channel posts (priority 1-2) to save Perplexity tokens
        all_posts = x_analysis_data.get("posts_content", [])
        x_evidence = [p for p in all_posts if p.get("priority", 3) <= 2]
        if x_evidence:
            print(f"[RESEARCH] Step 3b: Feeding {len(x_evidence)} news channel posts as evidence into Perplexity (skipped {len(all_posts) - len(x_evidence)} common posts)")
        else:
            print(f"[RESEARCH] Step 3b: No news channel posts to feed — running Perplexity without X evidence")

        # Step 3c: Run Perplexity WITH X evidence
        print(f"[RESEARCH] Step 3b: Perplexity Deep Search — starting...")
        research_data = None
        try:
            # Enhance query for events/policies to force recency
            claim_category = structured_claim.get("claim_category", "GENERAL")
            enhanced_query = f"{search_query} latest news" if claim_category in ["POLICY", "EVENT"] else search_query
            
            research_data = self.perplexity.deep_research(enhanced_query, structured_claim, x_evidence)
            print(f"[RESEARCH] Step 3b: Perplexity Deep Search complete")
        except Exception as e:
            print(f"[RESEARCH] Step 3b: Perplexity Deep Search failed ({str(e)})")
            research_data = {
                "summary": f"Research failed: {str(e)}",
                "findings": [],
                "sources": []
            }

        # Retry with alternative query if Perplexity returned nothing useful
        if not self._assess_perplexity_relevance(research_data):
            alt_query = self.structuring.create_alternative_query(structured_claim)
            if alt_query and alt_query != search_query:
                print(f"[RESEARCH] Perplexity returned no findings. Retrying with alternative query...")
                try:
                    # Also enhance the alternative query for recency
                    enhanced_alt = f"{alt_query} latest news" if claim_category in ["POLICY", "EVENT"] else alt_query
                    retry_data = self.perplexity.deep_research(enhanced_alt, structured_claim, x_evidence)
                    if self._assess_perplexity_relevance(retry_data):
                        research_data = retry_data
                        print(f"[RESEARCH] Retry successful — found relevant results")
                    else:
                        print(f"[RESEARCH] Retry also returned no findings")
                except Exception as e:
                    print(f"[RESEARCH] Retry failed: {str(e)}")

        # Step 3d: If Perplexity returned nothing useful, try Google News RSS
        news_data = None
        if not self._assess_perplexity_relevance(research_data):
            print(f"[RESEARCH] Step 3c: Perplexity returned no findings. Trying Google News RSS fallback...")
            try:
                # Use enhanced query if we have one, otherwise fallback to standard query logic
                news_data = self.news_search.search_news(enhanced_query if 'enhanced_query' in locals() else search_query, structured_claim)
                articles_found = news_data.get("articles_found", 0)
                tn_articles = news_data.get("tn_articles_found", 0)
                has_credible = news_data.get("has_credible_evidence", False)
                print(f"[RESEARCH] Step 3c: Google News found {articles_found} articles ({tn_articles} from TN), credible evidence: {has_credible}")
            except Exception as e:
                print(f"[RESEARCH] Step 3c: Google News RSS fallback failed: {str(e)}")
                news_data = None

        print(f"[RESEARCH] Research phase complete\n")

        return research_data, x_analysis_data, news_data

    def _generate_verdict(self, claim_text: str, structured_claim: dict, research_data: dict, x_analysis_data: dict = None, max_retries: int = 3, news_data: dict = None) -> dict:
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

                # Build X analysis context for verdict
                # Light summary when Perplexity succeeded; detailed posts when Perplexity failed
                perplexity_has_relevant = self._assess_perplexity_relevance(research_data)
                x_summary = self._build_x_summary(x_analysis_data)
                x_news_evidence = ""
                if not perplexity_has_relevant:
                    x_news_evidence = self._build_x_news_evidence(x_analysis_data)

                # Build Google News evidence for verdict (when available)
                news_evidence = ""
                if news_data and news_data.get("articles_found", 0) > 0:
                    news_evidence = self.news_search.format_for_verdict(news_data)

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
                claim_category = structured_claim.get("claim_category", "GENERAL")
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

                today_date = datetime.now().strftime("%B %d, %Y")

                verdict_prompt = f"""
You are a professional fact-checker with expertise across multiple domains. Evaluate the truthfulness of this claim using ALL available evidence: the research data below AND your own verified knowledge.

TODAY'S DATE: {today_date}

ORIGINAL INPUT: "{claim_text}"

{structured_context}

CLAIM METADATA:
- Claim Category: {claim_category}
- Claim Type: {claim_type.replace('_', ' ').title()}
- Geographic Scope: {geographic_scope.upper()}
- Location: {location if location else "Not specified"}

===============================================================================
RESEARCH (Perplexity Deep Search — includes X social media evidence as leads)
===============================================================================
RESEARCH SUMMARY:
{research_summary}

KEY FINDINGS:
{findings_text}

CREDIBLE SOURCES:
{sources_text}

RESEARCH LIMITATIONS:
{research_limitations if research_limitations else "None reported"}

X ANALYSIS NOTE: {x_summary}
{x_news_evidence}
{news_evidence}
{press_release_context}
===============================================================================
CLAIM CATEGORY (pre-classified): {claim_category}
===============================================================================

Category definitions:
- POLICY: Official actions, laws, budgets, government decisions, elections, appointments,
  regulations, taxes, schemes. → REQUIRE source evidence from official records, news reports,
  or government announcements. Your own knowledge alone is NOT sufficient.
- EVENT: Local or real-world incident at a specific place and time (protest, accident,
  arrest, fire, clash, strike). → REQUIRE source evidence. Your own knowledge is NOT sufficient.
- GENERAL: Scientific facts, history, technology, definitions, broad timeless knowledge.
  → CAN be verified using your own training knowledge from textbooks, encyclopedias,
  academic sources, and institutional records. Do NOT need recent news articles.

===============================================================================
STEP 1: CONTEXT EXTRACTION & SEARCH RELEVANCE VALIDATION
===============================================================================

FIRST, explicitly identify the claim's context:
- Country: (e.g., India)
- State/City: (e.g., Tamil Nadu, Chennai)
- Institution/Organization: (e.g., Election Commission of India, RBI)
- Person: (e.g., Finance Minister Thangam Thennarasu)
- Date/Time relevance: (e.g., February 2026)

THEN, validate research relevance:
Check whether the retrieved sources match the SAME place, institution, person, and topic
as the claim. Ask yourself:
- Do the sources discuss the correct state/city? (e.g., claim about Tamil Nadu → sources about Tamil Nadu, NOT Goa or Kerala)
- Do the sources discuss the correct institution/person?
- Do the sources discuss the correct time period?
- Do the sources discuss the correct topic/event?

If the sources are about a DIFFERENT location, entity, or topic than the claim:
→ Those sources are IRRELEVANT — do NOT use them as evidence for or against the claim
→ Set RETRIEVAL_MATCH to "NO" and explain the mismatch
→ This is a retrieval failure, NOT evidence that the claim is false or unverifiable

If the sources match the claim's context:
→ Set RETRIEVAL_MATCH to "YES"
→ Proceed to evidence assessment

===============================================================================
STEP 2: EVIDENCE ASSESSMENT
===============================================================================

EVIDENCE HIERARCHY (always prioritize in this order):
1. Official government / institutional records and press releases
2. Reputed news organizations (Reuters, BBC, The Hindu, NDTV, Times of India, etc.)
3. Research publications and academic sources
4. Social media / X posts from verified news channels (lowest priority)
Ignore unrelated trending topics even if keywords match.

FOR POLICY claims:
   - Evaluate research findings for official government records, gazette notifications, news reports
   - If research returned irrelevant results (wrong location, wrong entity, unrelated documents),
     do NOT treat them as evidence — note the mismatch
   - Note: X social media posts were used as research leads — their findings are included above
   - Check scope match: state-level policies may not appear in national/international media

FOR EVENT claims:
   - Evaluate research findings for direct evidence of the incident
   - If research returned irrelevant results (wrong location, wrong entity, homepage listings),
     do NOT treat them as evidence — note the mismatch
   - Check scope match: local events may not appear in national/international media

FOR GENERAL claims:
   - You ARE authorized to verify these from your training knowledge, BUT:
     * You MUST cite the specific authoritative source (institution, publication, or record)
     * You MUST state the exact verified fact — NOT just "well-established" or "well-known"
     * Example: "Marina Beach is approximately 6 km (not 13 km), according to Chennai Corporation records"
     * NOT: "Marina Beach is well-known to be one of the longest beaches"
   - Always prefer PRIMARY authoritative sources over secondary news articles:
     * Government/institutional body (Election Commission, RBI, ISRO) > news article
     * Official records/legislation > textbook reference
   - CRITICAL: If the retrieved sources do NOT contain information about the claim topic,
     DO NOT list those sources as evidence. Instead:
     * Acknowledge the sources are irrelevant ("Retrieved sources were government portals
       that do not contain specific information about [topic]")
     * If you can verify from training knowledge, cite the authoritative knowledge source
     * If you cannot confidently verify the SPECIFIC details (exact numbers, rankings,
       comparisons), mark as UNVERIFIED — not TRUE
   - NEVER mark as TRUE if you are unsure about specific quantitative claims
     (lengths, rankings, "one of the longest/biggest/first")
   - Only mark established knowledge as FALSE if it is demonstrably wrong

===============================================================================
SOURCE RELEVANCE VALIDATION (MANDATORY FOR ALL VERDICTS)
===============================================================================

Before listing ANY source in VERIFIED_SOURCES, verify:
1. Does this source contain SPECIFIC information about the claim topic?
   - Government homepages (chennai.nic.in, tn.gov.in) are NOT evidence unless they
     contain a specific page/document about the claim topic
   - General administrative portals are NOT evidence for specific factual claims
2. If a source is a generic homepage or portal without relevant content:
   → Do NOT list it as a verified source
   → Listing irrelevant sources is WORSE than listing fewer sources
3. Only list sources that DIRECTLY support or contradict the claim

BAD EXAMPLE (do NOT do this):
  Claim: "Marina Beach is 13 km long"
  WRONG: VERIFIED_SOURCES: chennai.nic.in, tn.gov.in  ← These don't mention beach length!

GOOD EXAMPLE:
  Claim: "Marina Beach is 13 km long"
  RIGHT: VERIFIED_SOURCES: Chennai Corporation tourism data, Guinness World Records (if applicable)

MANDATORY FOR ALL VERDICTS — PROVE, DON'T JUST ASSERT:
You MUST show the verified fact and compare it with the claim before concluding.
- For numbers/dates/amounts: "Claim says 234 seats → ECI delimitation records define 234 constituencies for TN Assembly → MATCH"
- For events: "Claim says GST implemented in 2017 → The 101st Constitutional Amendment Act enabled GST, launched July 1, 2017 → CONFIRMED"
- For knowledge: "Claim says TN Assembly has 234 seats → ECI records: 234 constituencies → MATCH"
NEVER just say "this is true" or "this is well-known" — always state the specific verified fact.

===============================================================================
STEP 3: VERDICT DETERMINATION
===============================================================================

✅ TRUE - Use when:
- [POLICY/EVENT] Credible external sources explicitly CONFIRM the claim (matching location/entity/topic)
- [GENERAL] The claim is verified knowledge — you can confirm from authoritative sources

❌ FALSE - ONLY when:
- Credible sources or established knowledge explicitly CONTRADICT the claim
- There must be POSITIVE EVIDENCE that the claim is wrong
- NEVER mark as FALSE because "no search results found"
- NEVER mark as FALSE based on sources about a different location/entity

⚠️ UNVERIFIED - Use when:
- [POLICY/EVENT] Relevant sources were searched (correct location/entity) but no confirmation found
- [GENERAL] RARELY — only if the claim is about obscure knowledge you cannot confidently verify
- Partial information: some parts confirmed, others cannot be verified
- IMPORTANT: NEVER output "Unverified" just because you failed to find relevant sources.
  First ensure the search retrieved sources about the CORRECT location/entity/topic.
  If sources were about the WRONG context, note it in the explanation as a search limitation.

===============================================================================
STEP 4: EXPLANATION RULES
===============================================================================

CONSISTENCY CHECK (do this BEFORE writing your response):
- If STATUS is TRUE → EXPLANATION must contain the specific proof/source that confirms it
  NEVER say TRUE and then write "no evidence was found" or "could not be verified"
- If STATUS is FALSE → EXPLANATION must contain the specific fact that contradicts it
- If STATUS is UNVERIFIED → EXPLANATION must NOT claim the fact is true or false
  If you find yourself writing proof in an UNVERIFIED explanation, change the status to TRUE

FOR TRUE VERDICTS — FORBIDDEN PHRASES IN EXPLANATION:
- NEVER use these phrases in a TRUE explanation, even as qualifiers or subordinate clauses:
  "was not found", "not found in", "could not be verified", "could not be confirmed",
  "no specific", "no verbatim", "no direct quote", "no explicit statement"
- RIGHT: "Multiple credible sources confirm Vijay publicly declared TVK's focus on the 2026 elections."
- WRONG: "While a verbatim quote was not found, evidence confirms the claim." ← the "not found" phrase will cause auto-correction to fail
- Behavioral evidence IS valid proof: if a leader hired a poll strategist, contested a constituency,
  and made public declarations about winning — that is confirmed intent, not "unverified".
  Treat behavioral evidence as direct confirmation for event/political claims.

FOR TRUE VERDICTS:
- [POLICY/EVENT] Cite the specific sources that confirm the claim
- [GENERAL] State the verified fact from the primary authority, then confirm it matches the claim.
  Example: "According to Election Commission of India records, Tamil Nadu Legislative Assembly has 234 constituencies. This matches the claim."
  NOT: "This is a well-established fact." (too vague, proves nothing)

FOR FALSE VERDICTS:
- Cite the specific evidence that contradicts the claim
- Show the comparison: "Claim states X, but verified records show Y"

FOR UNVERIFIED VERDICTS (POLICY/EVENT claims only):
- Confirm that sources about the CORRECT location/entity were searched
- If sources were about the wrong context, note the mismatch in explanation
- State what sources were searched and what was found
- Use: "This claim could not be independently verified through the online sources accessible to this system."
- NEVER use: "No credible sources were found" or "There is no evidence to support this claim"
- For local events, note that absence of national media coverage is expected

CRITICAL RULES:
1. [GENERAL] NEVER mark well-known facts as "Unverified" just because a web search didn't find articles. That is a SEARCH LIMITATION, not factual uncertainty.
2. "No search results" for GENERAL knowledge = search failure, NOT evidence of falsehood
3. [POLICY/EVENT] "no sources confirm X" = UNVERIFIED (not FALSE) — but ONLY if sources were about the correct context
4. If sources are about the WRONG location/entity, note it as a search limitation in your explanation
5. When in doubt between TRUE and UNVERIFIED for GENERAL claims, lean TRUE if you are confident
6. When in doubt between UNVERIFIED and FALSE for POLICY/EVENT, lean UNVERIFIED
7. Always show verified facts and compare numerically/logically with the claim before concluding

===============================================================================
STEP 3B: TEMPORAL AWARENESS (for POLICY/GOVERNMENT SCHEME claims)
===============================================================================

Government policies follow a publication timeline:
  Press conference / CM announcement → News reports → Official order (G.O.) → Gazette notification
  This process can take DAYS to WEEKS.

RULES:
1. News reports from credible outlets about a government announcement ARE VALID EVIDENCE.
   If The Hindu, TNIE, Dinamalar, Dinathanthi, NDTV, India Today, Times of India, or any
   credible news outlet reports a policy/scheme launch, that IS sufficient for a TRUE verdict.
2. "Not found in gazette" alone should NEVER yield FALSE or UNVERIFIED if news reports confirm it.
3. If news reports confirm the announcement but gazette hasn't been published yet:
   → Verdict: TRUE
   → Note in explanation: "Confirmed by news reports. Official gazette notification may follow."
4. Absence from gazette is EXPECTED for recent announcements — it is NOT negative evidence.

===============================================================================
STEP 3C: MULTI-SOURCE CORROBORATION SCORING
===============================================================================

Before determining your verdict, count and weigh the evidence:
- 3+ independent credible sources confirming → Strong TRUE (high confidence)
- 2 independent credible sources confirming → TRUE
- 1 credible news source confirming → TRUE (note the single source)
- Only social media/X posts → UNVERIFIED (needs corroboration from news outlets)
- Zero sources found → UNVERIFIED (not FALSE)

Tamil Nadu News Sources to check (treat any of these as credible evidence):
NEWSPAPERS: Dinamalar, Dinathanthi (Daily Thanthi), Dinamani, Maalai Malar, Tamil Murasu, The Hindu (TN), TNIE
TV CHANNELS: Sun News, Puthiya Thalaimurai, Thanthi TV, Polimer News, News7 Tamil, News18 Tamil Nadu, Kalaignar TV
MAGAZINES: Vikatan, Nakkheeran, Kumudam Reporter, Thuglak
ENGLISH: DT Next, Deccan Chronicle Chennai, Times of India Chennai, Business Line
ONLINE: Oneindia Tamil, Samayam Tamil, ABP Nadu, Tamil Guardian

If ANY of these sources report the claim, it qualifies as credible evidence for a TRUE verdict.
Do NOT require a government gazette when credible news outlets have already confirmed the claim.


Provide:
1. CONTEXT: Country, State/City, Institution, Person, Date (extracted from claim)
2. RETRIEVAL_MATCH: [YES/NO] — do the retrieved sources match the claim's context?
   If NO, explain the mismatch briefly.
3. EVIDENCE_SCORE: [0-5] — How many independent, credible sources DIRECTLY confirm this claim?
   0 = No sources found / LLM knowledge only (no external validation)
   1 = One source confirms
   2 = Two independent sources confirm
   3-5 = Three or more independent sources confirm
   RULES: Only count sources that contain SPECIFIC information about the claim.
   Do NOT count generic government portals or homepages. Do NOT count irrelevant sources.
4. STATUS: One of [✅ True, ❌ False, ⚠️ Unverified]
   EVIDENCE-VERDICT CONSISTENCY RULE:
   - If EVIDENCE_SCORE is 0 and claim is POLICY/EVENT → STATUS must be ⚠️ Unverified
   - If EVIDENCE_SCORE is 0 and claim is GENERAL → STATUS can be ✅ True ONLY if you cite
     a specific authoritative knowledge source (not "well-known")
   - If RETRIEVAL_MATCH is NO → do NOT base verdict on the irrelevant sources
5. EXPLANATION: Exactly 2-3 concise sentences. First sentence = verdict + key reason. Second sentence = supporting evidence or context. Do NOT include URLs in the explanation (those belong in VERIFIED_SOURCES). Do NOT repeat information from KEY_FINDINGS.
   CRITICAL: If STATUS is TRUE, explanation MUST cite the specific evidence. If sources
   don't support the claim, NEVER say TRUE.
6. KEY_FINDINGS: 3-5 bullet points of distinct, specific facts discovered during verification. Each finding must provide NEW information — never repeat what another finding already states. Never write "no results found" or "no specific articles" as a finding. If web research failed, provide useful verified facts from your own knowledge instead.
7. VERIFIED_SOURCES: ONLY list sources that contain SPECIFIC information about the claim.
   Do NOT list government homepages or portals that don't mention the claim topic.
   For GENERAL claims verified from knowledge, cite the PRIMARY authoritative body.
   If no relevant sources exist, write: "No directly relevant sources were retrieved."

Format your response EXACTLY as:
CONTEXT: Country: [country] | State/City: [state] | Institution: [institution] | Person: [person] | Date: [date]
RETRIEVAL_MATCH: [YES/NO] - [brief explanation if NO]
EVIDENCE_SCORE: [0-5]
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
                claim_context = ""
                retrieval_match = ""
                evidence_score = -1  # -1 means not provided
                gemini_findings = []
                gemini_sources = []

                lines = result_text.split('\n')
                current_section = None
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith("CONTEXT:"):
                        current_section = "context"
                        claim_context = stripped.replace("CONTEXT:", "").strip()
                    elif stripped.startswith("RETRIEVAL_MATCH:"):
                        current_section = "retrieval_match"
                        retrieval_match = stripped.replace("RETRIEVAL_MATCH:", "").strip()
                    elif stripped.startswith("EVIDENCE_SCORE:"):
                        current_section = "evidence_score"
                        score_text = stripped.replace("EVIDENCE_SCORE:", "").strip()
                        try:
                            evidence_score = int(re.search(r'\d+', score_text).group())
                        except:
                            evidence_score = -1
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

                if claim_context:
                    print(f"[Verdict] Claim context: {claim_context}")
                if retrieval_match:
                    print(f"[Verdict] Retrieval match: {retrieval_match}")
                print(f"[Verdict] Evidence score: {evidence_score}")
                print(f"[Verdict] Gemini findings: {len(gemini_findings)}, Gemini sources: {len(gemini_sources)}")

                # === POST-VERDICT CONSISTENCY VALIDATION ===
                # Auto-correct verdicts that contradict the evidence
                original_status = status
                is_true = "true" in status.lower()

                if is_true:
                    # Check 1: TRUE with evidence_score=0 for POLICY/EVENT → downgrade
                    if evidence_score == 0 and claim_category in ("POLICY", "EVENT"):
                        status = "⚠️ Unverified"
                        explanation = f"[Auto-corrected: evidence score 0 for {claim_category} claim] " + explanation
                        print(f"[Verdict] ⚠️ AUTO-CORRECTED: TRUE→Unverified (evidence_score=0, category={claim_category})")

                    # Check 2: TRUE but retrieval_match=NO → downgrade
                    elif retrieval_match.upper().startswith("NO"):
                        status = "⚠️ Unverified"
                        explanation = "[Auto-corrected: retrieved sources do not match claim context] " + explanation
                        print(f"[Verdict] ⚠️ AUTO-CORRECTED: TRUE→Unverified (retrieval_match=NO)")

                    # Check 3: TRUE but explanation contradicts it
                    else:
                        # Phrases that indicate the explanation truly contradicts a TRUE verdict
                        contradiction_phrases = [
                            "no evidence was found",
                            "could not be verified",
                            "no sources confirm",
                            "no specific articles",
                            "no credible sources",
                            "could not find",
                            "not found in",
                            "no relevant sources",
                            "sources do not contain",
                            "sources did not contain",
                            "retrieved sources were not relevant",
                        ]
                        # Phrases that indicate the explanation IS affirming the claim
                        # — if these are present, the contradiction phrase is just a minor qualifier
                        affirmative_phrases = [
                            "confirms",
                            "confirmed by",
                            "reported by",
                            "according to",
                            "credible sources",
                            "news reports",
                            "multiple sources",
                            "evidence confirms",
                            "publicly declared",
                            "publicly stated",
                            "announced",
                            "verified",
                        ]
                        explanation_lower = explanation.lower()
                        has_affirmative = any(p in explanation_lower for p in affirmative_phrases)
                        for phrase in contradiction_phrases:
                            if phrase in explanation_lower:
                                if has_affirmative:
                                    # The explanation says "while X was not found, Y confirms" — keep TRUE
                                    # but strip the qualifying clause so it doesn't confuse readers
                                    print(f"[Verdict] ℹ️ SKIPPED auto-correction: '{phrase}' found but affirmative evidence also present — keeping TRUE")
                                else:
                                    status = "⚠️ Unverified"
                                    explanation = f"[Auto-corrected: explanation contradicts TRUE verdict] " + explanation
                                    print(f"[Verdict] ⚠️ AUTO-CORRECTED: TRUE→Unverified (explanation contains '{phrase}', no affirmative counterpart)")
                                break

                if original_status != status:
                    print(f"[Verdict] Original status: {original_status} → Corrected to: {status}")

                # Use Perplexity sources if available, otherwise use Gemini's sources
                final_sources = sources if sources else gemini_sources

                return {
                    "status": status,
                    "explanation": explanation.strip(),
                    "sources": final_sources,
                    "gemini_findings": gemini_findings,
                    "gemini_sources": gemini_sources,
                    "claim_category": claim_category,
                    "claim_context": claim_context,
                    "retrieval_match": retrieval_match,
                    "evidence_score": evidence_score
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

    def _build_x_summary(self, x_analysis_data: dict) -> str:
        """
        Build a light X analysis summary for the verdict prompt.
        X evidence is already baked into Perplexity's research, so this is just informational.

        Args:
            x_analysis_data (dict): X analysis results

        Returns:
            str: Brief summary of X analysis
        """
        if not x_analysis_data:
            return "X analysis was not performed."

        if x_analysis_data.get("error"):
            return f"X analysis unavailable: {x_analysis_data.get('error')}"

        if not x_analysis_data.get("has_relevant_posts", False):
            return x_analysis_data.get("analysis_note", "No relevant X posts found.")

        posts_content = x_analysis_data.get("posts_content", [])
        posts_analyzed = x_analysis_data.get("posts_analyzed", 0)
        news_count = sum(1 for p in posts_content if p.get("priority", 3) <= 2)
        public_count = sum(1 for p in posts_content if p.get("priority", 3) == 3)

        summary = f"Found {posts_analyzed} posts."
        if news_count > 0:
            summary += f" {news_count} from news channels."
        if public_count > 0:
            summary += f" {public_count} from public accounts."
        summary += " This evidence was provided to Perplexity for research."

        return summary

    def _build_x_news_evidence(self, x_analysis_data: dict) -> str:
        """
        Build detailed X news evidence for the verdict prompt.
        Only called when Perplexity failed to find relevant results — surfaces
        credible news channel posts so Gemini can use them as evidence.

        Returns empty string if no news channel posts exist.
        """
        if not x_analysis_data or not x_analysis_data.get("has_relevant_posts", False):
            return ""

        posts_content = x_analysis_data.get("posts_content", [])
        news_posts = [p for p in posts_content if p.get("priority", 3) <= 2]

        if not news_posts:
            return ""

        lines = [
            "",
            "===============================================================================",
            "X NEWS CHANNEL EVIDENCE (Perplexity could not access/verify these — evaluate directly)",
            "===============================================================================",
            "The following posts are from RECOGNIZED NEWS OUTLETS on X. Perplexity's research",
            "could not find or access the linked articles, but these news channels are credible",
            "media sources whose reporting constitutes valid evidence.",
            "",
        ]

        for p in news_posts:
            text = p.get("text", "").replace("\n", " ")[:280]
            handle = p.get("author_handle", "?")
            date = p.get("date", "?")
            category = p.get("author_category", "unknown")
            label = "TAMIL NEWS" if category == "tamil_news" else "NATIONAL NEWS"
            lines.append(f"- [{label}] @{handle} ({date}): \"{text}\"")

        lines.append("")
        lines.append("EVIDENCE EVALUATION RULES FOR NEWS CHANNEL POSTS:")
        lines.append("- Reporting by recognized news outlets (Business Line, NDTV, Times of India,")
        lines.append("  The Hindu, India Today, etc.) IS sufficient evidence for:")
        lines.append("  * Statements/quotes attributed to ministers or officials")
        lines.append("  * Government projections, data, or announcements")
        lines.append("  * Event reports (inaugurations, launches, press conferences)")
        lines.append("- Do NOT require an official gazette or press release when multiple credible")
        lines.append("  news outlets are reporting the same claim.")
        lines.append("- 'Source not accessible by Perplexity' ≠ 'no evidence exists'")

        return "\n".join(lines)

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
            "findings": final_findings,
            "research_limitations": research_data.get("research_limitations", "")
        }

        # Only include research_summary when Perplexity returned relevant results
        if perplexity_relevant:
            response["research_summary"] = research_data.get("summary", "")

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
            posts_content = x_analysis_data.get("posts_content", [])
            news_posts = sum(1 for p in posts_content if p.get("priority", 3) <= 2)
            response["x_analysis"] = {
                "posts_analyzed": x_analysis_data.get("posts_analyzed", 0),
                "news_posts_found": news_posts,
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
