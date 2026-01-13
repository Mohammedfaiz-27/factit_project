#!/usr/bin/env python3
"""
Check if all required dependencies are installed
"""
import sys
import subprocess

def check_ffmpeg():
    """Check if FFmpeg is installed"""
    try:
        result = subprocess.run(['ffmpeg', '-version'],
                              capture_output=True,
                              text=True,
                              timeout=5)
        if result.returncode == 0:
            print("✓ FFmpeg is installed")
            return True
        else:
            print("✗ FFmpeg is not working properly")
            return False
    except FileNotFoundError:
        print("✗ FFmpeg is not installed")
        print("\nTo install FFmpeg:")
        print("  Windows: Download from https://ffmpeg.org/download.html")
        print("  Mac:     brew install ffmpeg")
        print("  Linux:   sudo apt-get install ffmpeg")
        return False
    except Exception as e:
        print(f"✗ Error checking FFmpeg: {str(e)}")
        return False

def check_python_packages():
    """Check if required Python packages are installed"""
    required = [
        'fastapi',
        'uvicorn',
        'google.genai',
        'PIL',
        'pydub',
        'dotenv'
    ]

    missing = []
    for package in required:
        try:
            if package == 'google.genai':
                __import__('google.genai')
            elif package == 'PIL':
                __import__('PIL')
            elif package == 'dotenv':
                __import__('dotenv')
            else:
                __import__(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} is not installed")
            missing.append(package)

    if missing:
        print(f"\nMissing packages: {', '.join(missing)}")
        print("Run: pip install -r requirments.txt")
        return False
    return True

def main():
    print("Checking dependencies...\n")

    print("Python Packages:")
    packages_ok = check_python_packages()

    print("\nSystem Dependencies:")
    ffmpeg_ok = check_ffmpeg()

    print("\n" + "="*50)
    if packages_ok and ffmpeg_ok:
        print("✓ All dependencies are installed!")
        return 0
    else:
        print("✗ Some dependencies are missing. Please install them.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
