# Multimodal Perplexity Deep Search Implementation

## Overview

This document describes the implementation of **Perplexity Deep Search** for multimodal content (images, videos, and audio files) in the fact-checker application.

## What Changed?

Previously:
- **Text claims** → Professional fact-checking pipeline with Perplexity Deep Search ✅
- **Images/Videos/Audio** → Basic Gemini analysis (no deep search) ❌

Now:
- **Text claims** → Professional fact-checking pipeline with Perplexity Deep Search ✅
- **Images** → OCR extraction → Professional pipeline with Deep Search ✅
- **Videos** → Speech-to-text + visual text → Professional pipeline with Deep Search ✅
- **Audio** → Speech-to-text → Professional pipeline with Deep Search ✅

## Architecture

### New Component: TextExtractionService

**File:** `backend/app/services/text_extraction_service.py`

This service handles content extraction from all media types:

1. **Images (OCR)**
   - Uses Gemini Vision to extract visible text
   - Captures visual context relevant to fact-checking
   - Inline processing (fast, no upload needed)

2. **Videos (Speech + Visual Text)**
   - Uploads video to Gemini Files API
   - Waits for processing (max 5 minutes)
   - Extracts both spoken dialogue and visible text
   - Returns comprehensive transcript

3. **Audio (Speech-to-Text)**
   - Converts WebM/other formats to WAV using pydub/FFmpeg
   - Uploads to Gemini Files API
   - Waits for processing (max 5 minutes)
   - Returns full transcription with key claims

### Updated Component: FactCheckService

**File:** `backend/app/services/fact_check_service.py`

The `check_multimodal_fact()` method now follows this pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│                   MULTIMODAL FACT-CHECK PIPELINE             │
└─────────────────────────────────────────────────────────────┘

Step 1: TEXT EXTRACTION
   ├─ Image  → OCR (Gemini Vision)
   ├─ Video  → Speech-to-text + visual text extraction
   └─ Audio  → Speech-to-text transcription

Step 2: CLAIM CONSTRUCTION
   ├─ If user provided text: User claim + extracted content as context
   └─ If no user text: Use extracted content as claim

Step 3: PROFESSIONAL FACT-CHECKING (8-step pipeline)
   ├─ 1. Input Moderation
   ├─ 2. Database Cache Check (SHA256 hash)
   ├─ 3. LLM Structuring (claim + entities + time period)
   ├─ 4. Perplexity Deep Research (credible sources)
   ├─ 5. Generate Verdict (✅ True / ❌ False / ⚠️ Unverified)
   ├─ 6. Output Moderation
   ├─ 7. Database Storage
   └─ 8. Return Response

Step 4: ENHANCED RESPONSE
   └─ Original response + media metadata + extracted text
```

### Frontend Updates

**File:** `frontend/src/components/FactCheckerResult.jsx`

The result component now displays:
- Media file indicator with emoji (📸 for images, 🎥 for videos, 🎤 for audio)
- Extracted content from the media
- Research summary from Perplexity
- Key findings from credible sources
- Sources with URLs
- Verdict with explanation

## Response Format

### Before (Old Multimodal Response)
```json
{
  "claim_text": "Media file: example.jpg",
  "verdict": "Basic analysis from Gemini...",
  "evidence": [],
  "media_type": "image/jpeg"
}
```

### After (New Multimodal Response)
```json
{
  "claim_text": "Claims from image: The Eiffel Tower is 324 meters tall",
  "status": "✅ True",
  "explanation": "The claim is accurate. The Eiffel Tower's height is 324 meters...",
  "sources": [
    "https://www.toureiffel.paris - Official Eiffel Tower website",
    "https://www.britannica.com/topic/Eiffel-Tower"
  ],
  "research_summary": "Research confirms the Eiffel Tower stands at 324 meters...",
  "findings": [
    "Original height was 300m, increased to 324m with antenna",
    "Confirmed by official Eiffel Tower documentation"
  ],
  "structured_claim": {
    "claim": "The Eiffel Tower is 324 meters tall",
    "entities": ["Eiffel Tower"],
    "time_period": "Current",
    "context": "Height measurement"
  },
  "media_type": "image/jpeg",
  "media_filename": "example.jpg",
  "extracted_text": "TEXT CONTENT: The Eiffel Tower is 324 meters tall\nVISUAL CONTEXT: Image shows the Eiffel Tower with height specification",
  "cached": false
}
```

## Key Benefits

### 1. Consistent Experience Across All Input Types
Users get the same professional, research-backed fact-checking whether they submit:
- Plain text
- An image with text
- A video with speech
- An audio recording

### 2. Credible Source Verification
All multimodal claims now go through Perplexity's deep research:
- Searches credible sources (Reuters, BBC, academic sources)
- Provides source URLs for verification
- Generates research summaries

### 3. Transparency
Users can see:
- What text was extracted from their media
- How the claim was structured
- What sources were consulted
- Key findings from research

### 4. Database Caching
Extracted claims are cached just like text claims:
- SHA256 hash-based lookup
- Instant results for duplicate media
- Saves API costs

## Testing

### 1. Start the Backend
```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 2. Start the Frontend
```bash
cd frontend
npm start
```

### 3. Test Cases

#### Image Test
1. Upload an image containing text (e.g., a news headline screenshot)
2. Verify OCR extraction appears in results
3. Check that Perplexity sources are shown

#### Video Test
1. Upload a short video with speech
2. Verify transcription is extracted
3. Check deep search results

#### Audio Test
1. Record voice memo with a claim
2. Verify speech-to-text works
3. Verify Perplexity research is performed

## Dependencies

### Required
- `google-generativeai` - For Gemini AI (OCR + transcription)
- `perplexity-api` - For deep research (already installed)
- `pydub` - For audio conversion (already installed)
- `FFmpeg` - System dependency for audio processing

### FFmpeg Installation
- **Windows**: Run `backend\install_ffmpeg_windows.bat` as Administrator
- **Mac**: `brew install ffmpeg`
- **Linux**: `sudo apt-get install ffmpeg`

## Code Structure

### New Files
- `backend/app/services/text_extraction_service.py` - Text extraction service
- `backend/test_multimodal.py` - Service initialization test
- `MULTIMODAL_DEEP_SEARCH.md` - This documentation

### Modified Files
- `backend/app/services/fact_check_service.py` - Refactored multimodal pipeline
- `frontend/src/components/FactCheckerResult.jsx` - Enhanced UI for multimodal results

## Performance Considerations

### Processing Times
- **Images**: ~3-5 seconds (OCR is fast)
- **Videos**: ~30-90 seconds (upload + processing + transcription)
- **Audio**: ~20-60 seconds (conversion + upload + transcription)

### Timeouts
- File upload processing: 5 minutes maximum
- Perplexity API calls: 30 seconds
- Total request timeout: 10 minutes (adjust in production)

### Cost Optimization
- Cache hits return instantly (no API calls)
- Images use inline processing (no upload needed)
- Videos/audio only uploaded once per file

## Error Handling

### Text Extraction Errors
- Returns error message in response
- Shows in UI with "❌ Error" status
- Logs details to backend console

### API Failures
- Graceful fallback to Gemini-only (if Perplexity unavailable)
- Retry logic with exponential backoff
- Clear error messages to user

### FFmpeg Missing
- Specific error message with installation instructions
- Audio conversion falls back to original format (may fail)
- User is informed to install FFmpeg

## Future Enhancements

1. **Multi-language Support**: Detect and translate non-English content
2. **Batch Processing**: Handle multiple files at once
3. **Real-time Processing**: Stream results as they become available
4. **Advanced OCR**: Support handwritten text, complex layouts
5. **Video Keyframe Analysis**: Fact-check visual claims, not just text
6. **Audio Speaker Diarization**: Identify who said what in multi-speaker audio

## Troubleshooting

### Issue: "FFmpeg not found"
**Solution**: Install FFmpeg (see INSTALL_FFMPEG.md), restart backend

### Issue: Video processing timeout
**Solution**:
- Check video format is supported (MP4, WebM, AVI)
- Ensure video is under 20MB
- Check internet connection (upload required)

### Issue: No sources returned
**Solution**:
- Verify `PERPLEXITY_API_KEY` is set in `.env`
- Check Perplexity API quota/limits
- Review extracted text quality (may be too vague)

### Issue: Extracted text is empty
**Solution**:
- For images: Verify image has visible text
- For videos: Ensure video has audio track
- For audio: Check audio quality/clarity

## Summary

This implementation extends the powerful Perplexity Deep Search feature to all media types, providing users with:
- Professional fact-checking for any content format
- Credible source verification
- Transparent extraction and research process
- Consistent user experience

The multimodal pipeline now matches the quality and rigor of text-based fact-checking, making the application truly comprehensive.
