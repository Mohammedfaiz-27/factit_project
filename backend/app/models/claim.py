from pydantic import BaseModel

class Claim(BaseModel):
    claim_text: str
    verdict: str  # 'true', 'false', 'unverified'
    evidence: list
