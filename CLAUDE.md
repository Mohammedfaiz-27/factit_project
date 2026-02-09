# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A professional multimodal fact-checking application that uses:
- **Google Gemini AI** (gemini-2.0-flash) for claim structuring and verdict generation
- **Perplexity AI** for deep research and source verification
- **X (Twitter) Analysis** for supplementary external source discovery
- **React 19** frontend with glassmorphism design
- **FastAPI** backend with layered architecture
- **MongoDB** for caching and persistence

The system implements an 8-step professional fact-checking pipeline with input/output moderation, database caching, LLM structuring, credible source verification, and X analysis for supplementary context.

## Development Commands

### Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt          # Install dependencies
python check_dependencies.py             # Verify dependencies are installed
uvicorn main:app --reload --port 8000    # Run development server
```

### Frontend (React)
```bash
cd frontend
npm install                              # Install dependencies
npm start                                # Run development server (port 3000)
npm run build                            # Build for production
npm test                                 # Run tests
```

### Prerequisites
- FFmpeg is required for audio processing (WebM to WAV conversion). See `INSTALL_FFMPEG.md` for installation instructions
- Windows quick install: Run `backend\install_ffmpeg_windows.bat` as Administrator
- Create `backend/.env` from `backend/.env.example` and configure:
  - `GEMINI_API_KEY` (required) - for claim structuring and verdict generation
  - `PERPLEXITY_API_KEY` (optional but recommended) - for deep research with credible sources
  - `X_BEARER_TOKEN` (optional) - for X (Twitter) analysis to discover additional sources
  - `MONGO_URI` (optional) - defaults to `mongodb://localhost:27017/factchecker_db`

## Architecture

### Backend Structure (FastAPI + Layered Architecture)

The backend follows a clean layered architecture with professional fact-checking pipeline:

1. **API Layer** (`app/api/claim_api.py`):
   - Two endpoints: `/api/claims/` (text) and `/api/claims/multimodal` (media)
   - Uses `asyncio.get_event_loop().run_in_executor()` to run blocking AI calls in threadpool
   - Text endpoint uses `ProfessionalFactCheckService` with 8-step pipeline

2. **Service Layer** - Multiple specialized services:

   **a) ProfessionalFactCheckService** (`app/services/professional_fact_check_service.py`):
   - **6-Step Pipeline** (unchanged structure, enhanced research):
     1. Database Cache Check - returns cached results if claim exists (SHA256 hash lookup)
     2. LLM Structuring - converts unstructured input to standardized schema
     3. Research Phase - **Parallel execution** of:
        - Perplexity Deep Research (PRIMARY) - queries credible sources (Reuters, BBC, etc.)
        - X Analysis (SUPPLEMENTARY) - extracts external links from X posts
     4. Generate Final Result - Gemini creates verdict using combined research context
        - Perplexity findings weighted HIGH
        - X-linked sources weighted LOW (supplementary only)
     5. Database Storage - saves structured data, research, verdict with timestamp
     6. Return Response - formatted result including `x_analysis` field

   **b) ModerationService** (`app/services/moderation_service.py`):
   - Input moderation using regex patterns + Gemini AI
   - Detects harmful content, illegal activities, PII (SSN, credit cards, emails)
   - Output moderation to prevent hallucinations and unsafe content

   **c) ClaimStructuringService** (`app/services/claim_structuring_service.py`):
   - **Structured Prompt Converter** - preprocessing step for all user inputs
   - Converts free-form queries/statements into standardized JSON schema:
     ```json
     {
       "task": "fact_check",
       "claim": "<clear factual statement>",
       "context": "<background info>",
       "entities": ["<names, organizations, locations>"],
       "time_period": "<specific year or time frame>",
       "output_format": "json"
     }
     ```
   - Transforms questions into factual statements (e.g., "did X do Y?" → "X did Y")
   - Extracts key entities, time periods, and contextual information
   - Generates optimized search queries for Perplexity from structured data
   - JSON-based extraction with fallback handling

   **d) PerplexityService** (`app/services/perplexity_service.py`):
   - Integrates with Perplexity API (llama-3.1-sonar-large-128k-online model)
   - Requests research from credible sources only
   - Parses summary, findings, and sources from responses
   - Includes fallback when API key not configured

   **e) XAnalysisService** (`app/services/x_analysis_service.py`):
   - Analyzes X (Twitter) for posts discussing the claim
   - **Runs in parallel** with Perplexity Deep Search during Step 3
   - Extracts only **external links** from posts (news articles, government portals, official sources)
   - X is **never treated as a source of truth**
   - Categorizes sources by credibility tier (primary, secondary, unknown)
   - Results passed to Gemini as **supplementary context** with low evidence weight
   - Engagement metrics (likes, retweets) are **never** used as evidence
   - Graceful fallback if X API unavailable - pipeline continues with Perplexity only

   **f) FactCheckService** (`app/services/fact_check_service.py`):
   - Legacy multimodal service for images/videos/audio
   - **Media Processing Strategy**:
     - **Images**: Processed directly inline using PIL (no upload needed)
     - **Videos**: Uploaded via `client.files.upload(file=path)`, polls for ACTIVE state (max 5 min)
     - **Audio**: Converted to WAV using pydub/FFmpeg, then uploaded and polled for ACTIVE state
   - All uploads wait for file processing: polls every 2s until state becomes ACTIVE

3. **Repository Layer** (`app/repository/claim_repository.py`):
   - **Cache System**: SHA256 hash-based claim lookup for instant cache hits
   - Stores: claim_hash, prompt, response, structured_data, research_data, timestamps
   - Methods: `find_cached_claim()`, `save()`, `get_recent_claims()`
   - Normalizes claims (lowercase, whitespace) before hashing

4. **Models** (`app/models/claim.py`):
   - Pydantic models for request/response validation

5. **Configuration** (`app/core/config.py`):
   - Loads environment variables from `.env` using `python-dotenv`
   - Configures Gemini API, Perplexity API, MongoDB, CORS settings

6. **Database** (`app/core/database.py`):
   - MongoDB connection setup using PyMongo
   - Collection: `claims` (stores prompts, responses, structured data, research, timestamps)

### Frontend Structure (React 19)

- **App.jsx**: Root component, manages result state
- **FactCheckerInput.jsx**: Handles user input (text/image/video/voice modes)
- **FactCheckerResult.jsx**: Displays fact-check results
- **services/api.js**: API client with two functions:
  - `checkClaim(claimText)`: Text-only fact checking
  - `checkMultimodalClaim(claimText, file)`: Multimodal fact checking with FormData
- Proxy configured in `package.json` to route `/api` requests to `http://localhost:8000`

### Key Technical Details

**Gemini Files API Usage:**
- Videos and audio require upload to Files API before processing
- Correct upload syntax: `client.files.upload(file='path')`
- Files transition: PROCESSING → ACTIVE (backend waits for this)
- Images use inline processing (faster, no upload needed)

**Audio Processing Pipeline:**
1. Browser records in WebM format
2. Backend converts WebM → WAV using pydub (requires FFmpeg)
3. Upload WAV to Gemini Files API
4. Wait for ACTIVE state
5. Process with Gemini for transcription + fact checking

**Async Pattern:**
- FastAPI endpoints are async but Gemini SDK is synchronous
- Solution: `await loop.run_in_executor(None, service.method, args)` runs sync code in threadpool
- Prevents blocking the event loop during long-running AI calls

**CORS Configuration:**
- Backend middleware allows requests from `FRONTEND_URL` (default: `http://localhost:3000`)
- Frontend proxy forwards `/api/*` to backend

## Important Notes

### Professional Fact-Checking Pipeline
- Text claims use the 6-step professional pipeline with parallel Perplexity + X research
- All user inputs pass through structured prompt conversion as preprocessing step
- Cache lookups use SHA256 hashing on normalized claims for instant results
- Response format: `{claim_text, status, explanation, sources, research_summary, findings, structured_claim, x_analysis}`
- `structured_claim` includes: `{claim, entities, time_period, context}` for transparency
- `x_analysis` includes: `{posts_analyzed, external_sources_found, sources, discussion_summary, note}`
- Status values: `✅ True`, `❌ False`, `⚠️ Unverified`, or `❌ Rejected` (moderation)

### X (Twitter) Analysis Integration
- **Purpose**: Surface additional external sources from X discussions, never opinions
- **Execution**: Runs in parallel with Perplexity Deep Search (no added latency)
- **Critical Rules**:
  - X is **never** a source of truth
  - Only external links (news, govt portals, official sources) are extracted
  - Engagement metrics (likes, retweets) are **ignored completely**
  - Virality/popularity is **never** treated as proof of accuracy
- **Evidence Weighting**:
  - Perplexity Deep Search = PRIMARY (high weight)
  - X-linked external sources = SUPPLEMENTARY (low weight)
- **Fallback**: If X API unavailable, pipeline continues with Perplexity only
- **Configuration**:
  - `X_BEARER_TOKEN` - Twitter API v2 bearer token
  - `X_ANALYSIS_ENABLED` - Enable/disable (default: true)
  - `X_SEARCH_LIMIT` - Max posts to analyze (default: 50)

### API Keys and Configuration
- `GEMINI_API_KEY` is required; backend will raise `ValueError` if not set
- `PERPLEXITY_API_KEY` is optional but recommended for deep research
  - Without it, system falls back to Gemini-only fact checking
  - Get key from: https://www.perplexity.ai/settings/api
- `X_BEARER_TOKEN` is optional for X analysis
  - Without it, X analysis returns fallback response and pipeline continues
  - Get token from: https://developer.twitter.com/en/portal/dashboard
- MongoDB is configured but the app can use in-memory storage if connection fails

### Performance and Timeouts
- File processing has timeouts: 5 minutes for video/audio uploads
- Audio conversion failures fall back to original format (may not work with Gemini)
- Perplexity API calls timeout after 60 seconds
- X Analysis API calls timeout after 30 seconds (runs in parallel, no added latency)
- Cache hits return instantly without API calls

### Security and Moderation
- Input moderation blocks harmful content, illegal activities, and PII
- Output moderation prevents hallucinations and unsafe responses
- All claims are normalized before hashing to prevent cache misses on formatting differences
