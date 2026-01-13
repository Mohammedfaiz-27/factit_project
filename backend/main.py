from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.claim_api import router as claim_router
from app.api.auth_api import router as auth_router
from app.core.config import FRONTEND_URL
import os

app = FastAPI()

# Configure CORS - Allow both local development and production frontend
allowed_origins = [
    FRONTEND_URL,  # From .env file
    "https://fact-checker-pi5i.vercel.app",  # Production Vercel URL
    "http://localhost:3000",  # Local development
]

# Remove duplicates and None values
allowed_origins = list(filter(None, set(allowed_origins)))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(claim_router, prefix="/api/claims", tags=["Fact Checking"])

@app.get("/")
async def root():
    return {"message": "Fact Checker API is running. Use /api/claims endpoint."}
