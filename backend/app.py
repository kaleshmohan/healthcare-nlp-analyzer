from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI()

HEALTHCARE_API = "http://healthcare-api:5000/text/analytics/v3.1/entities/health"

class TextRequest(BaseModel):
    text: str

@app.get("/")
def root():
    return {"message": "Backend is running"}

@app.post("/analyze")
def analyze_text(request: TextRequest):
    body = {
        "documents": [
            {
                "id": "1",
                "language": "en",
                "text": request.text
            }
        ]
    }

    response = requests.post(HEALTHCARE_API, json=body, timeout=60)
    response.raise_for_status()
    return response.json()