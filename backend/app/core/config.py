import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration settings for the app (Mongo URI etc.)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/factchecker_db")

# Google Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# OpenAI API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Perplexity API Configuration
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# X (Twitter) Analysis Configuration
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")
X_ANALYSIS_ENABLED = os.getenv("X_ANALYSIS_ENABLED", "true").lower() == "true"
X_SEARCH_LIMIT = int(os.getenv("X_SEARCH_LIMIT", "10"))

# Server Configuration
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")

# JWT Authentication Configuration
import secrets
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
