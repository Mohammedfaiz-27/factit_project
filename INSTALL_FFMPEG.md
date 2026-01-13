# Installing FFmpeg on Windows

FFmpeg is required for audio format conversion (WebM to WAV) to ensure compatibility with Gemini API.

## Quick Installation (Recommended)

### Option 1: Using Chocolatey (Easiest)

1. Open PowerShell as Administrator
2. Install Chocolatey if you don't have it:
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```

3. Install FFmpeg:
```powershell
choco install ffmpeg
```

4. Restart your terminal/IDE

### Option 2: Manual Installation

1. **Download FFmpeg**:
   - Go to: https://github.com/BtbN/FFmpeg-Builds/releases
   - Download: `ffmpeg-master-latest-win64-gpl.zip`

2. **Extract the files**:
   - Extract to: `C:\ffmpeg`
   - You should have: `C:\ffmpeg\bin\ffmpeg.exe`

3. **Add to System PATH**:
   - Press `Win + R`, type `sysdm.cpl`, press Enter
   - Go to "Advanced" tab → "Environment Variables"
   - Under "System variables", find "Path" → Click "Edit"
   - Click "New" and add: `C:\ffmpeg\bin`
   - Click "OK" on all windows

4. **Verify Installation**:
   Open a NEW terminal (important!) and run:
   ```bash
   ffmpeg -version
   ```
   You should see FFmpeg version information.

5. **Restart your backend server**:
   ```bash
   cd backend
   uvicorn main:app --reload --port 8000
   ```

## Testing

After installation, run:
```bash
cd backend
python check_dependencies.py
```

You should see:
```
✓ FFmpeg is installed
```

## Troubleshooting

### "Couldn't find ffmpeg or avconv"
- Make sure you added FFmpeg to PATH
- Close and reopen your terminal/IDE
- Verify with: `ffmpeg -version`

### Still not working?
- Restart your computer (PATH changes require restart)
- Make sure the path is exactly: `C:\ffmpeg\bin` (not `C:\ffmpeg`)
- Check that `ffmpeg.exe` exists in that folder

## Alternative: Skip Audio Conversion

If you can't install FFmpeg, you can modify the code to skip conversion and use original formats (less reliable with WebM files).
