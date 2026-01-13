# Fact Checker App

A multimodal fact-checking application that uses Google Gemini AI to verify claims from text, images, videos, and audio.

## Features

- **Text Fact Checking**: Verify text-based claims
- **Image Analysis**: Upload images and fact-check visual claims
- **Video Analysis**: Process videos and verify claims within them
- **Audio Transcription**: Upload audio files for transcription and fact-checking
- **Voice Recording**: Record audio directly in the browser

## Tech Stack

### Backend
- FastAPI
- Google Gemini AI (gemini-2.0-flash)
- Python 3.8+
- MongoDB (optional - currently using in-memory storage)

### Frontend
- React 19
- Modern CSS with glassmorphism effects

## Setup Instructions

### Prerequisites

1. Python 3.8 or higher
2. Node.js 14 or higher
3. FFmpeg (required for audio/voice recording)
   - **Windows**:
     - Quick: Run `backend\install_ffmpeg_windows.bat` (as Administrator)
     - Or: `choco install ffmpeg` (requires Chocolatey)
     - Manual: See [INSTALL_FFMPEG.md](INSTALL_FFMPEG.md)
   - **Mac**: `brew install ffmpeg`
   - **Linux**: `sudo apt-get install ffmpeg`
4. A Google Gemini API key (get it from [Google AI Studio](https://makersuite.google.com/app/apikey))
5. (Optional) An OpenAI API key for future features (get it from [OpenAI Platform](https://platform.openai.com/api-keys))

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Check if all dependencies are installed:
```bash
python check_dependencies.py
```

4. Configure environment variables:
   - Copy `.env.example` to `.env`
   - Edit `.env` and add your Gemini API key:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```

5. Run the backend server:
```bash
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm start
```

The app will open at `http://localhost:3000`

## Environment Variables

All environment variables are configured in `backend/.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Your Google Gemini API key | (required) |
| `OPENAI_API_KEY` | Your OpenAI API key (optional) | None |
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017/factchecker_db` |
| `BACKEND_PORT` | Backend server port | `8000` |
| `BACKEND_HOST` | Backend server host | `0.0.0.0` |
| `FRONTEND_URL` | Frontend URL for CORS | `http://localhost:3000` |
| `GEMINI_MODEL` | Gemini model to use | `gemini-2.0-flash` |

## How It Works

### File Processing Approach

The application uses different methods to process different file types optimally:

- **Images** (JPEG, PNG, GIF, WebP):
  - Processed directly inline using PIL
  - No file upload required
  - Fast and efficient for image analysis

- **Videos** (MP4, MOV, AVI):
  - Uploaded to Gemini Files API using `client.files.upload(file=path)`
  - Server waits for video processing to complete (up to 5 minutes)
  - Supports longer processing times for larger videos

- **Audio** (WebM, MP3, WAV, M4A):
  - Browser recordings (WebM) are automatically converted to WAV format using FFmpeg
  - Converted audio is uploaded to Gemini Files API
  - System waits for file to reach ACTIVE state before processing
  - Supports transcription and fact-checking
  - Works with browser voice recordings
  - Typical processing time: 5-30 seconds for short audio clips
  - Fallback: If conversion fails, original format is used

## Usage

1. **Text Fact Checking**:
   - Select "Text" mode
   - Enter your claim
   - Click "Check Fact"

2. **Image Fact Checking**:
   - Select "Image/Video" mode
   - Upload an image file
   - Optionally add context or a specific claim
   - Click "Check Fact"

3. **Video Fact Checking**:
   - Select "Image/Video" mode
   - Upload a video file
   - Optionally add context or a specific claim
   - Click "Check Fact"
   - Note: Videos may take longer to process

4. **Voice Recording**:
   - Select "Voice" mode
   - Click "Start Recording"
   - Speak your claim
   - Click "Stop Recording"
   - Optionally add text context
   - Click "Check Fact"

## API Endpoints

### POST `/api/claims/`
Check a text-based claim.

**Request Body:**
```json
{
  "claim_text": "Your claim here"
}
```

### POST `/api/claims/multimodal`
Check a multimodal claim (text, image, video, or audio).

**Request Body (multipart/form-data):**
- `claim_text` (optional): Text claim or context
- `file` (optional): Image, video, or audio file

**Response:**
```json
{
  "claim_text": "Your claim",
  "verdict": "Fact check result",
  "evidence": [],
  "media_type": "image/jpeg"
}
```

## Troubleshooting

### Backend Issues

1. **"GEMINI_API_KEY environment variable is not set"**:
   - Make sure you have created a `.env` file in the `backend` directory
   - Verify your API key is correctly set in the `.env` file

2. **Import errors**:
   - Ensure all dependencies are installed: `pip install -r requirments.txt`
   - Make sure you're using Python 3.8 or higher

3. **Video processing takes too long**:
   - Large video files may take several minutes to process
   - The backend waits up to 5 minutes for Gemini to finish processing
   - If processing takes longer, you'll get a timeout error
   - Try using shorter videos or smaller file sizes

4. **Image upload errors**:
   - Images are now processed directly (not uploaded to Files API)
   - Supported formats: JPEG, PNG, GIF, WebP
   - If you get PIL errors, ensure the `pillow` package is installed

5. **"Files.upload() takes 1 positional argument but 2 were given"**:
   - This has been fixed in the latest version
   - The correct API signature is `client.files.upload(file='path/to/file')`
   - Make sure you have the latest `google-genai` package installed: `pip install --upgrade google-genai`

6. **Voice recording not working**:
   - Audio files (including voice recordings) are now properly uploaded using the Files API
   - Supported audio formats: WebM, MP3, WAV, M4A
   - Browser recordings typically use WebM format by default
   - The system now waits for audio files to be processed before use

7. **"File is not in an ACTIVE state" error**:
   - This has been fixed - the system now properly waits for files to be processed
   - Both audio and video files go through a PROCESSING → ACTIVE state transition
   - The backend polls every 2 seconds until the file is ACTIVE (up to 5 minutes max)
   - If you still see this error, the file may have failed processing - check the logs

8. **"Failed to convert server response to JSON" for voice recordings**:
   - This has been fixed - audio files are now converted to WAV format before upload
   - Make sure FFmpeg is installed on your system
   - The system automatically converts WebM (browser recordings) to WAV for better compatibility
   - Check backend logs for conversion status

### Frontend Issues

1. **CORS errors**:
   - Ensure the backend is running on port 8000
   - Check that `FRONTEND_URL` in `.env` matches your frontend URL

2. **File upload not working**:
   - Check browser console for errors
   - Ensure the file type is supported (images: jpg, png, gif; videos: mp4, mov, avi)
   - Check file size limits (Gemini API has file size restrictions)

## Development

### File Structure

```
fact-checker-app/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── claim_api.py        # API endpoints
│   │   ├── core/
│   │   │   ├── config.py           # Configuration and env vars
│   │   │   └── database.py         # Database setup
│   │   ├── models/
│   │   │   └── claim.py            # Data models
│   │   ├── repository/
│   │   │   └── claim_repository.py # Data access layer
│   │   └── services/
│   │       └── fact_check_service.py # Business logic
│   ├── main.py                     # FastAPI app entry point
│   ├── requirments.txt             # Python dependencies
│   ├── .env                        # Environment variables (not in git)
│   └── .env.example                # Example env file
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── FactCheckerInput.jsx   # Input component
│   │   │   └── FactCheckerResult.jsx  # Result display
│   │   ├── services/
│   │   │   └── api.js                 # API client
│   │   ├── App.jsx                    # Main app component
│   │   ├── App.css                    # Styles
│   │   └── index.js                   # Entry point
│   └── package.json                   # Node dependencies
└── README.md                          # This file
```

## Security Notes

- Never commit your `.env` file to version control
- The `.env.example` file is provided as a template
- Keep your Gemini API key secure and don't share it publicly
- Consider implementing rate limiting in production
- Add authentication if deploying publicly

## License

ISC

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
