import asyncio
from fastapi import APIRouter, File, UploadFile, Form, Depends
from typing import Optional
from pydantic import BaseModel
from app.services.fact_check_service import FactCheckService
from app.services.professional_fact_check_service import ProfessionalFactCheckService
from app.middleware.auth_middleware import get_current_user_id

router = APIRouter()
service = FactCheckService()
professional_service = ProfessionalFactCheckService()

class ClaimInput(BaseModel):
    claim_text: str

class URLInput(BaseModel):
    url: str

@router.post("/")
async def check_claim(data: ClaimInput):
    # Run blocking check_fact in threadpool to prevent blocking event loop
    # Using professional service with full pipeline
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, professional_service.check_fact, data.claim_text)
    return result

@router.post("/multimodal")
async def check_multimodal_claim(
    claim_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """
    Handle multimodal fact checking: text, images, videos, and audio files
    """
    if not claim_text and not file:
        return {"error": "Either claim_text or file must be provided"}

    loop = asyncio.get_event_loop()

    if file:
        # Read file content
        file_content = await file.read()
        result = await loop.run_in_executor(
            None,
            service.check_multimodal_fact,
            claim_text or "",
            file_content,
            file.content_type,
            file.filename
        )
    else:
        # Text only
        result = await loop.run_in_executor(None, service.check_fact, claim_text)

    return result

@router.post("/url")
async def check_url_claim(data: URLInput):
    """
    Handle fact checking from a URL/link.
    Extracts article content and fact-checks the main claims.
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, service.check_url_fact, data.url)
    return result
