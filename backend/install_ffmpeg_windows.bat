@echo off
echo ========================================
echo FFmpeg Installation for Windows
echo ========================================
echo.

:: Check if FFmpeg is already installed
where ffmpeg >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo FFmpeg is already installed!
    ffmpeg -version | findstr "ffmpeg version"
    echo.
    echo If the backend still shows errors, try restarting it.
    pause
    exit /b 0
)

echo FFmpeg is not found in PATH.
echo.
echo Choose installation method:
echo.
echo 1. Install using Chocolatey (Recommended - Automatic)
echo 2. Manual installation (Download and setup PATH)
echo.
set /p choice="Enter your choice (1 or 2): "

if "%choice%"=="1" goto chocolatey
if "%choice%"=="2" goto manual
echo Invalid choice.
pause
exit /b 1

:chocolatey
echo.
echo Installing FFmpeg using Chocolatey...
echo.

:: Check if Chocolatey is installed
where choco >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Chocolatey is not installed.
    echo Installing Chocolatey first...
    echo.
    echo This requires Administrator privileges.
    echo Please run this script as Administrator!
    pause
    exit /b 1
)

echo Installing FFmpeg...
choco install ffmpeg -y

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo FFmpeg installed successfully!
    echo ========================================
    echo.
    echo Please RESTART your terminal/IDE and the backend server.
    echo.
) else (
    echo.
    echo Installation failed. Try manual installation instead.
    echo.
)
pause
exit /b 0

:manual
echo.
echo Manual Installation Steps:
echo.
echo 1. Download FFmpeg from: https://github.com/BtbN/FFmpeg-Builds/releases
echo    Look for: ffmpeg-master-latest-win64-gpl.zip
echo.
echo 2. Extract to: C:\ffmpeg
echo.
echo 3. Add to PATH:
echo    - Press Win+R, type: sysdm.cpl
echo    - Advanced tab ^> Environment Variables
echo    - System variables ^> Path ^> Edit
echo    - New ^> Add: C:\ffmpeg\bin
echo    - OK to save
echo.
echo 4. Restart your terminal and backend server
echo.
echo 5. Verify with: ffmpeg -version
echo.
echo Opening download page...
start https://github.com/BtbN/FFmpeg-Builds/releases
echo.
pause
exit /b 0
