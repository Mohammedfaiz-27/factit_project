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

    def deep_research(self, search_query: str, structured_claim: dict, x_evidence: list = None) -> dict:
        """
        Perform deep research using Perplexity AI.

        Args:
            search_query (str): Optimized search query
            structured_claim (dict): Structured claim data
            x_evidence (list): Optional list of X posts to use as research leads

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
            claim_type = structured_claim.get('claim_type', 'other')
            geographic_scope = structured_claim.get('geographic_scope', 'national')
            location = structured_claim.get('location', '')

            original_input = structured_claim.get('original_input', '')

            # Format entities for display
            entities_text = ', '.join(entities) if entities else 'N/A'

            # Check if original input is in a regional language
            is_regional_language = any(ord(c) > 127 for c in original_input.replace(' ', '')) if original_input else False

            # Build domain-specific source guidance based on claim type
            source_guidance = self._get_source_guidance(claim_type, geographic_scope, location)

            research_prompt = f"""
You are a professional fact-checker. Research the following claim using the DOMAIN-APPROPRIATE sources listed below.

CLAIM TYPE: {claim_type.replace('_', ' ').upper()}
GEOGRAPHIC SCOPE: {geographic_scope.upper()}
LOCATION: {location if location else 'Not specified'}

{source_guidance}

CRITICAL RESEARCH RULES:
1. The absence of coverage from international or national English-language outlets does NOT mean a local event did not occur.
2. District-level events in India are typically ONLY covered by regional language media and local reporters.
3. SOURCE RELEVANCE MANDATE: DO NOT cite newspaper homepages, generic government portals (like chennai.nic.in, tn.gov.in), or directories as "sources". Only list URLs that point to a SPECIFIC article, document, or page discussing the claim.
4. If your search returns only generic homepages without specific claim information, state explicitly: "Retrieved sources were generic and did not contain specific information."
5. NEVER confuse "listing URLs that exist" with "finding coverage in those URLs."
6. RECENCY MANDATE: For political news, local events, or policy announcements, ALWAYS prioritize the most recent articles (last 24h to 7d). Use your search engine's recency filters if necessary. Do not rely solely on old or historical articles if the claim sounds like breaking news.

CLAIM CATEGORY HANDLING:
A) For SPECIFIC EVENTS (protests, accidents, appointments, scheme launches):
   - Requires specific news articles, press releases, or official announcements
   - If no specific articles found, state: "No specific articles or reports about this event were found."

B) For GENERAL KNOWLEDGE / ESTABLISHED FACTS (economic data, geographic facts, institutional roles, historical facts, industry/sector information):
   - You may use reference sources: government data portals, economic surveys, industry reports, institutional websites, Wikipedia with citations, established databases
   - These do NOT require a specific "news article" — official statistics pages, government reports, and reference data ARE valid sources
   - If the claim is well-documented general knowledge supported by multiple reference sources, report what you know with citations
   - Example: "Tamil Nadu is a manufacturing hub" can be verified via government economic data, IBEF reports, Make in India portal, industry association data — these ARE credible sources even if they're not "news articles"

Claim (English): {claim}
{"" if not is_regional_language else f"Claim (Original Language): {original_input[:300]}"}

Additional Details:
- Key Entities: {entities_text}
- Time Period: {time_period if time_period else 'Not specified'}
- Context: {context if context else 'None provided'}

Search Query: {search_query}

{"IMPORTANT: This claim is originally in a regional language. Search for this claim using BOTH the English translation AND the original regional language text. Regional newspapers and news websites publish in the regional language, so searching only in English will miss most relevant coverage. Try searching key names and terms in the original language on regional news websites." if is_regional_language else ""}

{self._format_x_evidence(x_evidence) if x_evidence else ""}

Provide:
1. A summary of what was ACTUALLY FOUND (not what sources exist in general)
2. Key findings (3-5 bullet points) — only include findings with SPECIFIC evidence
3. List of SPECIFIC sources used (with URLs when available) — only sources that contained actual information about THIS claim
4. SCOPE: Whether this is a LOCAL, STATE, NATIONAL, or INTERNATIONAL event
5. RESEARCH_LIMITATIONS: What types of sources could NOT be accessed that would be relevant for this claim type

Format your response EXACTLY as:
SUMMARY: [brief summary of what was actually found]
SCOPE: [LOCAL/STATE/NATIONAL/INTERNATIONAL]
FINDINGS:
- [finding 1]
- [finding 2]
- [finding 3]
SOURCES:
- [source 1]
- [source 2]
RESEARCH_LIMITATIONS: [what sources were inaccessible or not searched that would be relevant]
"""

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional fact-checking assistant with access to real-time information. Match your source selection to the SCOPE of the claim: use regional/local language media for district-level events, state-level outlets for state events, and national/international sources for national/international events. For Indian local events, prioritize regional language newspapers (Tamil, Hindi, Telugu, etc.), district police/administration releases, and local TV channels. Never dismiss a local claim simply because international outlets don't cover it. IMPORTANT: When a search query contains both English and regional language text (separated by |), search using BOTH languages. Regional language keywords help you find articles in local media that publish in that language (e.g., Tamil newspapers publish in Tamil, not English). Search the regional language terms on regional news sites."
                    },
                    {
                        "role": "user",
                        "content": research_prompt
                    }
                ],
                "temperature": 0.2,  # Lower temperature for more factual responses
                "max_tokens": 2000
            }

            print(f"[Perplexity] Making API request for: {search_query[:50]}...")
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            print(f"[Perplexity] Response status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                research_text = result['choices'][0]['message']['content']
                print(f"[Perplexity] Got response ({len(research_text)} chars)")
                print(f"[Perplexity] First 500 chars: {research_text[:500]}")

                # Parse the response
                parsed_result = self._parse_research_response(research_text)
                print(f"[Perplexity] Parsed: {len(parsed_result.get('findings', []))} findings, {len(parsed_result.get('sources', []))} sources")

                # Debug: if parsing failed, show why
                if len(parsed_result.get('findings', [])) == 0:
                    print(f"[Perplexity] DEBUG - Has SUMMARY: {'SUMMARY:' in research_text}")
                    print(f"[Perplexity] DEBUG - Has FINDINGS: {'FINDINGS:' in research_text}")
                    print(f"[Perplexity] DEBUG - Has bullet (-): {'-' in research_text}")

                return parsed_result
            else:
                print(f"[Perplexity] API error: {response.status_code} - {response.text}")
                return self._fallback_research(search_query)

        except requests.exceptions.Timeout:
            print("Perplexity API timeout")
            return self._fallback_research(search_query)
        except Exception as e:
            print(f"Perplexity research error: {str(e)}")
            return self._fallback_research(search_query)

    def _get_source_guidance(self, claim_type: str, geographic_scope: str, location: str) -> str:
        """
        Generate domain-specific and scope-specific source guidance for the research prompt.

        Args:
            claim_type (str): Type of claim (protest_arrest, accident_death, etc.)
            geographic_scope (str): Geographic scope (local, district, state, national, international)
            location (str): Specific location

        Returns:
            str: Formatted source guidance for the prompt
        """
        # Determine if location is in India (for regional language media guidance)
        is_india = any(term in location.lower() for term in [
            "india", "tamil nadu", "kerala", "karnataka", "andhra",
            "telangana", "maharashtra", "delhi", "uttar pradesh",
            "bihar", "bengal", "rajasthan", "gujarat", "punjab",
            "haryana", "madhya pradesh", "odisha", "assam",
            "jharkhand", "chhattisgarh", "goa", "manipur",
            "meghalaya", "mizoram", "nagaland", "sikkim",
            "tripura", "arunachal", "himachal", "uttarakhand",
        ]) if location else False

        is_tamil_nadu = any(term in location.lower() for term in [
            "tamil nadu", "chennai", "coimbatore", "madurai", "trichy",
            "salem", "tirunelveli", "erode", "vellore", "thanjavur",
            "dindigul", "kanchipuram", "tiruppur", "cuddalore",
            "perambalur", "pudukkottai", "karur", "ariyalur",
            "nagapattinam", "ramanathapuram", "sivaganga",
            "virudhunagar", "theni", "tenkasi", "tirupattur",
            "ranipet", "chengalpattu", "kallakurichi", "villupuram",
            "krishnagiri", "dharmapuri", "nilgiris", "namakkal",
        ]) if location else False

        # Domain-specific source hierarchy
        # NOTE: News reports and press releases are prioritized ABOVE gazette
        # documents because policies/schemes are announced in news BEFORE
        # being gazetted (lag of days to weeks).
        domain_sources = {
            "protest_arrest": {
                "priority_1": "Tamil Nadu news channels and newspapers: Dinamalar, Dinathanthi (Daily Thanthi), Dinamani, Maalai Malar, Vikatan, Tamil Murasu, Kumudham, Ananda Vikatan, Junior Vikatan, Nakkheeran, Kumudam Reporter, Thuglak, DT Next, The New Indian Express (TN edition), The Hindu (TN section)",
                "priority_2": "Tamil Nadu TV news channels: Sun News, Puthiya Thalaimurai, Thanthi TV, Polimer News, News7 Tamil, Kalaignar TV News, Jaya TV News, News18 Tamil Nadu, Captain News, Vasanth TV, Raj News Tamil, Lotus News, Malai Murasu TV, Adithya TV, Peppers TV",
                "priority_3": "District police press releases, SP/Commissioner statements, FIR records, District Collector/administration statements",
                "priority_4": "Wire services (PTI, ANI), state-level and national media (NDTV, India Today, Times of India)",
                "priority_5": "Tamil online news portals: Oneindia Tamil, Samayam Tamil, Tamil Guardian, Asianet News Tamil, ABP Nadu, Zee Tamil News, News Tamil 24x7",
            },
            "accident_death": {
                "priority_1": "Tamil Nadu news channels: Sun News, Puthiya Thalaimurai, Thanthi TV, Polimer News, News7 Tamil (TV channels are often FIRST to report accidents with footage)",
                "priority_2": "Tamil newspapers: Dinamalar, Dinathanthi, Dinamani, Maalai Malar, DT Next, Tamil Murasu with district reporters",
                "priority_3": "FIR records, police station reports, traffic police statements, hospital statements",
                "priority_4": "State-level media, PTI/ANI wire service reports, The Hindu, TNIE",
                "priority_5": "Tamil online portals: Oneindia Tamil, Samayam Tamil, ABP Nadu, News18 Tamil Nadu",
            },
            "government_scheme": {
                "priority_1": "Tamil Nadu news articles and reports: The Hindu (Tamil Nadu section), The New Indian Express (TN edition), DT Next, Dinamalar, Dinathanthi, Dinamani, Times of India (Chennai edition), Deccan Chronicle (Chennai), Business Line, Financial Express",
                "priority_2": "PIB India releases, Tamil Nadu state government press releases, CM press conferences, minister statements reported in media",
                "priority_3": "Tamil TV news coverage: Sun News, Puthiya Thalaimurai, Thanthi TV, Polimer News, News7 Tamil, News18 Tamil Nadu",
                "priority_4": "District Collectorate press releases, official social media, department websites (tn.gov.in)",
                "priority_5": "Government gazette notifications and official G.O.s (NOTE: gazettes often lag behind announcements by days to weeks — absence from gazette does NOT mean the policy is false)",
            },
            "heritage_environment": {
                "priority_1": "Tamil Nadu news coverage: The Hindu, TNIE, Dinamalar, Dinathanthi, Dinamani, Vikatan reporting on heritage/environment",
                "priority_2": "ASI (Archaeological Survey of India) or State Archaeology Department statements, Forest Department",
                "priority_3": "Expert statements from historians, archaeologists, environmental scientists",
                "priority_4": "Heritage/environment journalism outlets, specialized publications",
                "priority_5": "Regional TV news channels (Sun News, Puthiya Thalaimurai, Thanthi TV) and national media",
            },
            "politics": {
                "priority_1": "Tamil Nadu news media: Dinamalar, Dinathanthi, Dinamani, The Hindu, TNIE, DT Next, Vikatan, Nakkheeran, Thuglak for TN politics",
                "priority_2": "Tamil TV news: Sun News, Puthiya Thalaimurai, Thanthi TV, Polimer News, News7 Tamil, News18 Tamil Nadu, Kalaignar TV",
                "priority_3": "PTI, ANI wire services, official party statements",
                "priority_4": "National media (NDTV, India Today, Times of India), Election Commission records",
                "priority_5": "Tamil online news: Oneindia Tamil, Samayam Tamil, ABP Nadu, Tamil Guardian",
            },
            "crime": {
                "priority_1": "Tamil Nadu crime reporting: Dinamalar, Dinathanthi, Nakkheeran (known for crime journalism), Dinamani, DT Next",
                "priority_2": "Tamil TV news crime coverage: Sun News, Puthiya Thalaimurai, Thanthi TV, Polimer News, News7 Tamil",
                "priority_3": "Police press releases, FIR records, court records, ecourts.gov.in",
                "priority_4": "National media for high-profile cases (NDTV, India Today, The Hindu)",
                "priority_5": "Wire services (PTI, ANI), fact-checking organizations",
            },
            "health_science": {
                "priority_1": "WHO, ICMR, relevant health ministry statements, peer-reviewed journals",
                "priority_2": "Tamil Nadu health news: The Hindu, TNIE, Dinamalar reporting on health/science, DT Next health section",
                "priority_3": "Tamil TV health coverage: Sun News, Puthiya Thalaimurai, News7 Tamil health segments",
                "priority_4": "Science/health journalists at major outlets, institutional press releases",
                "priority_5": "Fact-checking organizations (Alt News, Boom Live)",
            },
        }

        sources = domain_sources.get(claim_type, {
            "priority_1": "Official government or institutional sources",
            "priority_2": "Wire services (PTI, ANI, Reuters, AP)",
            "priority_3": "National and regional media",
            "priority_4": "Domain-specific expert sources",
            "priority_5": "Fact-checking organizations",
        })

        # Build scope-aware guidance
        scope_note = ""
        if geographic_scope in ("local", "district"):
            scope_note = f"""
IMPORTANT SCOPE NOTE: This is a {geographic_scope.upper()}-level claim. For {geographic_scope}-level events in India:
- National/international outlets (Reuters, BBC, AP) almost NEVER cover these events — their absence means NOTHING.
- Regional language newspapers are the PRIMARY source — they have district-level reporters who cover every significant local event.
- District police and administration press notes are often the most authoritative source."""

            if is_tamil_nadu:
                scope_note += """
- For Tamil Nadu specifically, search ALL of these news sources:
  NEWSPAPERS: Dinamalar (dinamalar.com), Dinathanthi/Daily Thanthi (dailythanthi.com), Dinamani (dinamani.com), Maalai Malar (maalaimalar.com), Tamil Murasu, Kumudham, The Hindu Tamil (tamil.thehindu.com)
  MAGAZINES: Vikatan (vikatan.com), Ananda Vikatan, Junior Vikatan, Nakkheeran (nakkheeran.in), Kumudam Reporter, Thuglak
  TV CHANNELS: Sun News, Puthiya Thalaimurai (puthiyathalaimurai.com), Thanthi TV (thanthitv.com), Polimer News (polimernews.com), News7 Tamil (news7tamil.live), Kalaignar TV News, Captain News, News18 Tamil Nadu, Jaya TV News, Raj News Tamil
  ENGLISH DAILIES (TN editions): The Hindu, The New Indian Express, DT Next (dtnext.in), Deccan Chronicle Chennai, Times of India Chennai, Business Line
  ONLINE PORTALS: Oneindia Tamil (tamil.oneindia.com), Samayam Tamil (tamil.samayam.com), ABP Nadu, Asianet News Tamil, Zee Tamil News, News Tamil 24x7, Tamil Guardian"""

        guidance = f"""
DOMAIN-SPECIFIC SOURCE HIERARCHY (search in this priority order):
1. {sources.get('priority_1', 'Official sources')}
2. {sources.get('priority_2', 'Wire services')}
3. {sources.get('priority_3', 'Regional media')}
4. {sources.get('priority_4', 'Broader media')}
5. {sources.get('priority_5', 'Other credible sources')}
{scope_note}"""

        return guidance

    def _format_x_evidence(self, x_evidence: list) -> str:
        """
        Format X posts as an evidence section for the research prompt.

        Posts are grouped by author category (Tamil news, National news, Public).
        """
        if not x_evidence:
            return ""

        tamil_posts = [p for p in x_evidence if p.get("author_category") == "tamil_news"]
        national_posts = [p for p in x_evidence if p.get("author_category") == "national_news"]
        common_posts = [p for p in x_evidence if p.get("author_category") == "common_people"]

        lines = [
            "===============================================================================",
            "X (SOCIAL MEDIA) EVIDENCE — Posts found discussing this claim:",
            "===============================================================================",
        ]

        if tamil_posts:
            lines.append("[TAMIL NEWS CHANNELS]")
            for p in tamil_posts:
                text = p.get("text", "").replace("\n", " ")[:140]
                lines.append(f"- @{p.get('author_handle', '?')} ({p.get('date', '?')}): \"{text}\"")
            lines.append("")

        if national_posts:
            lines.append("[NATIONAL NEWS CHANNELS]")
            for p in national_posts:
                text = p.get("text", "").replace("\n", " ")[:140]
                lines.append(f"- @{p.get('author_handle', '?')} ({p.get('date', '?')}): \"{text}\"")
            lines.append("")

        if common_posts:
            lines.append("[PUBLIC POSTS]")
            for p in common_posts:
                text = p.get("text", "").replace("\n", " ")[:140]
                lines.append(f"- @{p.get('author_handle', '?')} ({p.get('date', '?')}): \"{text}\"")
            lines.append("")

        lines.append("Use these X posts as LEADS for your research. Verify the claims made in these posts")
        lines.append("using credible sources. Posts from news channels are more reliable than common users.")
        lines.append("If news channel posts report specific facts, try to find the original articles or sources.")

        return "\n".join(lines)

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
        scope = ""
        research_limitations = ""

        # Split into sections
        lines = research_text.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()
            # Remove markdown bold formatting (**text** -> text)
            clean_line = line.replace("**", "")

            if clean_line.startswith("SUMMARY:"):
                current_section = "summary"
                summary = clean_line.replace("SUMMARY:", "").strip()
            elif clean_line.startswith("SCOPE:"):
                current_section = "scope"
                scope = clean_line.replace("SCOPE:", "").strip()
            elif clean_line.startswith("FINDINGS:"):
                current_section = "findings"
            elif clean_line.startswith("SOURCES:"):
                current_section = "sources"
            elif clean_line.startswith("RESEARCH_LIMITATIONS:") or clean_line.startswith("RESEARCH LIMITATIONS:"):
                current_section = "research_limitations"
                research_limitations = clean_line.split(":", 1)[1].strip() if ":" in clean_line else ""
            elif line.startswith("-") or line.startswith("•") or line.startswith("*"):
                # Handle bullet points (-, •, or * for markdown lists)
                content = line.lstrip("-•*").strip()
                # Also remove any leading ** from bold bullets
                if content.startswith("**"):
                    content = content[2:]
                if current_section == "findings" and content:
                    findings.append(content)
                elif current_section == "sources" and content:
                    sources.append(content)
                elif current_section == "research_limitations" and content:
                    research_limitations += " " + content
            elif current_section == "summary" and line and not clean_line.startswith("Verdict"):
                summary += " " + line
            elif current_section == "research_limitations" and line:
                research_limitations += " " + line

        return {
            "summary": summary.strip(),
            "findings": findings,
            "sources": sources,
            "scope": scope,
            "research_limitations": research_limitations.strip()
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
                "Please configure PERPLEXITY_API_KEY in your .env file",
                "please check you perplexity api key credits"
            ],
            "sources": []
        }
