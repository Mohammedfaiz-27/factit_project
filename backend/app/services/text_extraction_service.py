from google import genai
from google.genai import types
from PIL import Image
from app.core.config import GEMINI_API_KEY, GEMINI_MODEL
import tempfile
import os
import time
from pydub import AudioSegment


class TextExtractionService:
    """
    Service for extracting text from multimodal content:
    - OCR for images
    - Speech-to-text for videos and audio
    """

    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL

    def extract_text_from_image(self, file_content: bytes, filename: str) -> dict:
        """
        Extract text from image using OCR (Gemini Vision).

        Args:
            file_content (bytes): Image file content
            filename (str): Filename for logging

        Returns:
            dict: {"text": extracted_text, "error": error_message (if any)}
        """
        temp_file_path = None
        try:
            # Save file temporarily
            suffix = os.path.splitext(filename)[1] if filename else '.jpg'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            # Use Gemini Vision for OCR
            print(f"Extracting text from image: {filename}")
            image = Image.open(temp_file_path)
            chat = self.client.chats.create(model=self.model)

            ocr_prompt = """
Extract all visible text from this image. Include:
1. Any text visible in the image (signs, captions, documents, etc.)
2. Brief description of visual content if relevant to understanding the context
3. Any claims or statements being made

If there is no text, describe the visual content that might be relevant for fact-checking.

Format your response as:
TEXT CONTENT: [extracted text or "No text found"]
VISUAL CONTEXT: [brief description of relevant visual elements]
"""

            response = chat.send_message([ocr_prompt, image])
            extracted_text = response.text.strip()

            print(f"Text extracted successfully from image")
            return {"text": extracted_text, "error": None}

        except Exception as e:
            error_msg = f"Error extracting text from image: {str(e)}"
            print(error_msg)
            return {"text": "", "error": error_msg}

        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except:
                    pass

    def extract_text_from_video(self, file_content: bytes, filename: str) -> dict:
        """
        Extract text from video (transcribe audio + OCR any visible text).

        Args:
            file_content (bytes): Video file content
            filename (str): Filename for logging

        Returns:
            dict: {"text": extracted_text, "error": error_message (if any)}
        """
        temp_file_path = None
        try:
            # Save file temporarily
            suffix = os.path.splitext(filename)[1] if filename else '.mp4'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            print(f"Extracting text from video: {filename}")
            print(f"Uploading video to Gemini Files API...")

            # Upload video to Gemini Files API
            uploaded_file = self.client.files.upload(file=temp_file_path)
            print(f"Video uploaded successfully: {uploaded_file.name}")

            # Wait for processing
            max_wait = 300  # 5 minutes
            waited = 0
            while uploaded_file.state.name == "PROCESSING" and waited < max_wait:
                time.sleep(2)
                waited += 2
                uploaded_file = self.client.files.get(name=uploaded_file.name)
                print(f"Video processing state: {uploaded_file.state.name} (waited {waited}s)")

            if uploaded_file.state.name == "FAILED":
                raise ValueError("Video processing failed. Check if format is supported.")
            elif uploaded_file.state.name == "PROCESSING":
                raise ValueError(f"Video processing timeout after {max_wait} seconds")
            elif uploaded_file.state.name != "ACTIVE":
                raise ValueError(f"File is in {uploaded_file.state.name} state, expected ACTIVE")

            print("Video is now ACTIVE. Extracting text...")

            # Extract text using Gemini
            chat = self.client.chats.create(model=self.model)
            extraction_prompt = """
Analyze this video and extract:
1. TRANSCRIPT: All spoken words and dialogue
2. VISUAL TEXT: Any text visible in the video (signs, captions, overlays, etc.)
3. KEY CLAIMS: Any factual claims or statements made

Format your response as:
TRANSCRIPT: [transcribed speech or "No speech detected"]
VISUAL TEXT: [visible text or "No text visible"]
KEY CLAIMS: [main claims to fact-check]
"""

            response = chat.send_message([extraction_prompt, uploaded_file])
            extracted_text = response.text.strip()

            print("Text extracted successfully from video")
            return {"text": extracted_text, "error": None}

        except FileNotFoundError as fnf_error:
            error_msg = (
                "FFmpeg is not installed or not in PATH. "
                "Video processing requires FFmpeg.\n"
                "Please install FFmpeg: See INSTALL_FFMPEG.md"
            )
            print(f"ERROR: {error_msg}")
            return {"text": "", "error": error_msg}

        except Exception as e:
            error_msg = f"Error extracting text from video: {str(e)}"
            print(error_msg)
            return {"text": "", "error": error_msg}

        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except:
                    pass

    def extract_text_from_audio(self, file_content: bytes, filename: str, content_type: str) -> dict:
        """
        Extract text from audio using speech-to-text.

        Args:
            file_content (bytes): Audio file content
            filename (str): Filename for logging
            content_type (str): MIME type of the audio

        Returns:
            dict: {"text": extracted_text, "error": error_message (if any)}
        """
        temp_file_path = None
        wav_path = None
        try:
            # Save file temporarily
            suffix = os.path.splitext(filename)[1] if filename else '.webm'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            print(f"Extracting text from audio: {filename}")

            # Convert to WAV for better compatibility
            try:
                print("Converting audio to WAV format...")
                audio = AudioSegment.from_file(temp_file_path)
                wav_path = temp_file_path.replace(os.path.splitext(temp_file_path)[1], '.wav')
                audio.export(wav_path, format="wav")
                final_file_path = wav_path
                print("Audio converted successfully to WAV")
            except FileNotFoundError as fnf_error:
                error_msg = (
                    "FFmpeg is not installed or not in PATH. "
                    "Audio conversion requires FFmpeg.\n"
                    "Please install FFmpeg:\n"
                    "  Windows: See INSTALL_FFMPEG.md in the project root\n"
                    "  Quick: choco install ffmpeg (requires Chocolatey)\n"
                    "After installation, restart the server."
                )
                print(f"ERROR: {error_msg}")
                raise ValueError(error_msg)
            except Exception as conv_error:
                print(f"Audio conversion failed: {str(conv_error)}")
                print("WARNING: Using original format may not work with Gemini API")
                final_file_path = temp_file_path

            # Upload to Gemini Files API
            print("Uploading audio to Gemini Files API...")
            uploaded_file = self.client.files.upload(file=final_file_path)
            print(f"Audio uploaded successfully: {uploaded_file.name}")

            # Wait for processing
            max_wait = 300  # 5 minutes
            waited = 0
            while uploaded_file.state.name == "PROCESSING" and waited < max_wait:
                time.sleep(2)
                waited += 2
                uploaded_file = self.client.files.get(name=uploaded_file.name)
                print(f"Audio processing state: {uploaded_file.state.name} (waited {waited}s)")

            if uploaded_file.state.name == "FAILED":
                raise ValueError("Audio processing failed. Check if format is supported.")
            elif uploaded_file.state.name == "PROCESSING":
                raise ValueError(f"Audio processing timeout after {max_wait} seconds")
            elif uploaded_file.state.name != "ACTIVE":
                raise ValueError(f"File is in {uploaded_file.state.name} state, expected ACTIVE")

            print("Audio is now ACTIVE. Transcribing...")

            # Transcribe using Gemini
            chat = self.client.chats.create(model=self.model)
            transcription_prompt = """
Transcribe this audio and extract:
1. FULL TRANSCRIPT: Complete transcription of all spoken words
2. KEY CLAIMS: Any factual statements or claims made
3. CONTEXT: Speaker information or context if identifiable

Format your response as:
TRANSCRIPT: [full transcription]
KEY CLAIMS: [main claims to fact-check]
CONTEXT: [relevant context]
"""

            response = chat.send_message([transcription_prompt, uploaded_file])
            extracted_text = response.text.strip()

            print("Text extracted successfully from audio")
            return {"text": extracted_text, "error": None}

        except Exception as e:
            error_msg = f"Error extracting text from audio: {str(e)}"
            print(error_msg)
            return {"text": "", "error": error_msg}

        finally:
            # Clean up temporary files
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            if wav_path and os.path.exists(wav_path):
                try:
                    os.unlink(wav_path)
                except:
                    pass
