# Link Feature Documentation

## Overview

The **Link feature** allows users to fact-check claims from news articles and web pages by simply pasting a URL. The system automatically extracts the article content, identifies main factual claims, and verifies them using Perplexity Deep Search.

## Feature Goal

Users can paste a website or news article link, and the system will:
1. ✅ Fetch and extract the article text from the URL
2. ✅ Identify the main factual claim(s) using AI
3. ✅ Pass extracted claims through the professional fact-checking pipeline
4. ✅ Return verdict (✅ True / ❌ False / ⚠️ Unverified)

## How It Works

### User Flow

```
User pastes URL (e.g., https://news.example.com/article)
         ↓
System fetches webpage content
         ↓
BeautifulSoup parses HTML and extracts article text
         ↓
Gemini AI identifies main factual claim(s)
         ↓
Professional Fact-Checking Pipeline (8 steps):
  1. Input Moderation
  2. Database Cache Check
  3. LLM Structuring
  4. Perplexity Deep Research ← Verifies with credible sources
  5. Generate Verdict
  6. Output Moderation
  7. Database Storage
  8. Return Response
         ↓
Display results with verdict, sources, and article info
```

### Technical Pipeline

```python
URL → URLExtractionService → FactCheckService → ProfessionalFactCheckService
                ↓                      ↓                        ↓
         [Extract Content]     [Combine Context]    [Deep Research + Verdict]
                ↓                      ↓                        ↓
         Article Text         Main Claim + Context    Verdict + Sources
```

## Architecture

### Backend Components

#### 1. URLExtractionService
**File:** `backend/app/services/url_extraction_service.py`

Handles URL content extraction and claim identification:

**Methods:**
- `extract_from_url(url)` - Main extraction method
  - Validates URL format
  - Fetches webpage with proper headers
  - Parses HTML using BeautifulSoup
  - Extracts article text from common containers
  - Uses Gemini to identify main claims

**Features:**
- **Smart Article Detection**: Looks for common article containers (`<article>`, `.article-content`, `.post-content`, etc.)
- **Fallback Extraction**: If no article container found, extracts all paragraphs
- **Text Cleaning**: Removes scripts, styles, navigation, ads, and extra whitespace
- **AI Claim Extraction**: Uses Gemini to identify factual claims from article
- **Error Handling**: Handles timeouts, connection errors, HTTP errors gracefully

**Response Format:**
```python
{
    "text": "Full article text...",
    "main_claim": "The primary factual claim to verify",
    "title": "Article Title",
    "source": "example.com",
    "error": None  # or error message if failed
}
```

#### 2. FactCheckService.check_url_fact()
**File:** `backend/app/services/fact_check_service.py`

Integrates URL extraction with professional fact-checking:

**Pipeline:**
1. Extract content from URL using `URLExtractionService`
2. Validate extraction succeeded
3. Construct claim with article context
4. Pass to `ProfessionalFactCheckService` (includes Perplexity Deep Search)
5. Add URL metadata to response

**Response Enhancement:**
```python
{
    # Standard fact-check fields
    "claim_text": "Main claim from article...",
    "status": "✅ True",
    "explanation": "...",
    "sources": [...],
    "research_summary": "...",
    "findings": [...],

    # URL-specific metadata
    "url": "https://example.com/article",
    "article_title": "Article Title",
    "article_source": "example.com",
    "article_preview": "First 500 chars..."
}
```

#### 3. API Endpoint
**File:** `backend/app/api/claim_api.py`

New endpoint: `POST /api/claims/url`

**Request Body:**
```json
{
  "url": "https://example.com/article"
}
```

**Usage:**
```python
@router.post("/url")
async def check_url_claim(data: URLInput):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, service.check_url_fact, data.url)
    return result
```

### Frontend Components

#### 1. Input Mode Selection
**File:** `frontend/src/components/FactCheckerInput.jsx`

Added "Link" button alongside Text, Image/Video, and Voice modes.

**Features:**
- URL input field with validation (type="url")
- Clear placeholder: "Enter article URL (e.g., https://example.com/article)"
- Automatic routing to URL endpoint when Link mode is selected

#### 2. API Service
**File:** `frontend/src/services/api.js`

New function: `checkURLClaim(url)`

```javascript
export async function checkURLClaim(url) {
  const res = await fetch(`${API_BASE_URL}/api/claims/url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: url }),
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}
```

#### 3. Result Display
**File:** `frontend/src/components/FactCheckerResult.jsx`

Enhanced to show URL-specific information:

**Display Elements:**
- 🔗 Source URL (clickable link)
- Article title
- Publisher/source domain
- Main claim extracted
- Verdict with explanation
- Research summary from Perplexity
- Key findings
- Credible sources with URLs

## Dependencies

### New Dependencies

Added to `requirements.txt`:
```
beautifulsoup4  # HTML parsing
```

### Existing Dependencies (Used)
```
requests        # HTTP requests to fetch URLs
google-genai    # Gemini AI for claim extraction
fastapi         # API endpoints
```

## Installation

### Backend Setup

1. Install new dependency:
```bash
cd backend
pip install beautifulsoup4
```

Or install all dependencies:
```bash
pip install -r requirements.txt
```

2. Verify installation:
```bash
python test_url_feature.py
```

Expected output:
```
SUCCESS: URL fact-checking feature ready!
```

### Frontend Setup

No additional dependencies needed. The feature uses existing React setup.

## Usage Examples

### Example 1: News Article

**Input URL:**
```
https://www.bbc.com/news/science-environment-12345678
```

**Process:**
1. System fetches BBC article
2. Extracts article text (title, content)
3. Gemini identifies main claim: "Scientists discover new planet in habitable zone"
4. Perplexity researches credible sources
5. Returns verdict with sources

**Output:**
```json
{
  "url": "https://www.bbc.com/news/...",
  "article_title": "New Planet Found in Habitable Zone",
  "article_source": "bbc.com",
  "claim_text": "Scientists discover new planet in habitable zone...",
  "status": "✅ True",
  "explanation": "The claim is accurate. Multiple credible sources confirm...",
  "sources": [
    "https://www.nasa.gov/...",
    "https://www.nature.com/..."
  ],
  "research_summary": "Research confirms discovery published in Nature...",
  "findings": [
    "Planet discovered by NASA's TESS telescope",
    "Located 100 light-years away in habitable zone"
  ]
}
```

### Example 2: Blog Post

**Input URL:**
```
https://blog.example.com/health-miracle-cure
```

**Process:**
1. System extracts blog post content
2. Identifies claim: "New supplement cures all diseases"
3. Perplexity searches medical sources
4. Returns verdict based on research

**Output:**
```json
{
  "status": "❌ False",
  "explanation": "No scientific evidence supports this claim. Medical authorities warn against...",
  "sources": [
    "https://www.mayoclinic.org/...",
    "https://www.nih.gov/..."
  ]
}
```

### Example 3: Error Handling

**Invalid URL:**
```
not-a-valid-url
```

**Output:**
```json
{
  "status": "❌ Error",
  "explanation": "Invalid URL format. Please provide a complete URL (e.g., https://example.com)"
}
```

**JavaScript-Only Site:**
```json
{
  "status": "❌ Error",
  "explanation": "Could not extract meaningful content from this URL. The page may require JavaScript or have restricted access."
}
```

## Supported URL Types

### ✅ Supported
- News articles (BBC, Reuters, CNN, NYTimes, etc.)
- Blog posts with text content
- Wikipedia articles
- Academic articles with accessible text
- Magazine articles
- Opinion pieces
- Press releases

### ⚠️ Limited Support
- JavaScript-heavy single-page apps (may not extract content)
- Paywalled content (only free preview text)
- Social media posts (platform-dependent)

### ❌ Not Supported
- PDF files (use file upload instead)
- Video-only content (use video upload mode)
- Audio podcasts (use audio upload mode)
- Login-required pages
- CAPTCHA-protected sites

## Error Handling

### Common Errors

1. **Invalid URL Format**
   - Error: "Invalid URL format. Please provide a complete URL"
   - Solution: Ensure URL starts with http:// or https://

2. **Connection Timeout**
   - Error: "Request timeout. The website took too long to respond."
   - Solution: Try again or check if website is accessible

3. **No Content Extracted**
   - Error: "Could not extract meaningful content from this URL"
   - Solution: Website may be JavaScript-only or have restricted access

4. **HTTP Errors**
   - Error: "HTTP error 404. The website returned an error."
   - Solution: Verify URL is correct and page exists

### Timeout Settings

- **Request timeout**: 15 seconds (configurable in URLExtractionService)
- **Total processing**: ~30-60 seconds (includes extraction + AI analysis + deep search)

## Performance Considerations

### Speed
- **Fast URLs**: ~5-10 seconds (simple articles)
- **Average**: ~15-30 seconds (complex articles + deep research)
- **Slow**: ~30-60 seconds (large articles + comprehensive research)

### Caching
- Results are cached based on extracted claim
- If same claim appears in different articles, cache hit occurs
- Cache lookup is instant (no re-processing)

### Rate Limiting
Consider adding rate limiting for URL requests to prevent:
- Abuse (scraping many URLs rapidly)
- Server overload
- API quota exhaustion

Suggested limits:
- 10 URL checks per minute per IP
- 100 URL checks per day per user

## Security Considerations

### Input Validation
- ✅ URL format validation using `urlparse`
- ✅ Scheme validation (only http/https allowed)
- ✅ Timeout to prevent hanging requests

### Content Safety
- ✅ Input moderation (checks extracted claims)
- ✅ Output moderation (ensures safe responses)
- ✅ User-Agent header (identifies bot for transparency)

### Recommendations
1. **Add URL allowlist/blocklist**: Prevent checking malicious domains
2. **Implement rate limiting**: Prevent abuse
3. **Add content-length limits**: Prevent memory exhaustion
4. **Log suspicious activity**: Monitor for scraping attempts

## Testing

### Manual Testing

1. Start the servers:
```bash
# Terminal 1 - Backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend
npm start
```

2. Test cases:

**Test 1: BBC News Article**
- URL: https://www.bbc.com/news/technology (any recent article)
- Expected: Extracts article, identifies claim, returns verdict

**Test 2: Wikipedia**
- URL: https://en.wikipedia.org/wiki/Eiffel_Tower
- Expected: Extracts content, identifies factual claim, verifies

**Test 3: Invalid URL**
- URL: `not-a-url`
- Expected: Error message about invalid format

**Test 4: 404 Error**
- URL: https://example.com/nonexistent-page-123456
- Expected: HTTP 404 error message

### Automated Testing

Run the test script:
```bash
cd backend
python test_url_feature.py
```

Expected output:
```
SUCCESS: URL fact-checking feature ready!
```

## Future Enhancements

### Planned Features
1. **PDF Support**: Extract claims from linked PDF documents
2. **Multi-language Support**: Translate non-English articles before fact-checking
3. **Historical Archive**: Check claims using Wayback Machine for deleted content
4. **Related Articles**: Show other articles making similar claims
5. **Claim Tracking**: Track how claims evolve over time across different sources

### Advanced Features
1. **Batch URL Checking**: Check multiple URLs at once
2. **Browser Extension**: Right-click any article to fact-check
3. **RSS Feed Monitoring**: Auto-check new articles from monitored sources
4. **API Webhook**: Notify when specific claims appear in new articles
5. **Citation Network**: Show how sources cite each other

## Troubleshooting

### Issue: "Could not extract meaningful content"

**Possible Causes:**
- Website uses JavaScript to load content
- Content is behind a login wall
- Website blocks scrapers

**Solutions:**
1. Try a different URL from the same publication
2. Use direct article links (not homepage)
3. For JS-heavy sites, consider using a headless browser (future enhancement)

### Issue: "No factual claims identified"

**Possible Causes:**
- Article is purely opinion-based
- Content is too short
- Article is narrative-only (no verifiable facts)

**Solutions:**
1. Ensure URL points to article with factual claims
2. Avoid opinion pieces or editorials
3. Try URLs with specific facts, statistics, or events

### Issue: Slow processing

**Possible Causes:**
- Large article with lots of text
- Website responds slowly
- Deep research takes time

**Solutions:**
1. Wait patiently (up to 60 seconds)
2. Check network connection
3. Try a shorter article

## Summary

The Link feature seamlessly extends the fact-checker to handle web content:

**Benefits:**
- ✅ No manual copy-paste needed
- ✅ Automatic claim identification
- ✅ Full context from article preserved
- ✅ Same rigorous fact-checking as text input
- ✅ Source attribution (original article + verification sources)

**Use Cases:**
- Verify claims in news articles
- Check blog posts for accuracy
- Validate social media shared links
- Research scientific articles
- Investigate viral stories

The feature maintains the same high quality and rigor as the existing text/multimodal fact-checking, now accessible directly from any URL.
