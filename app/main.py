'''
Main FastAPI application for phone agent
Handles incoming calls from Twilio
'''

from fastapi import FastAPI,Request,Response
from fastapi.responses import PlainTextResponse
import os
from dotenv import load_dotenv

load_dotenv()

# Create FastAPI app
app = FastAPI(title="Phone Agent API", version="1.0.0")

@app.get("/")
async def read_root():
    """Health check endpoint"""
    return {"status": "running", "service": "phone-agent","message": "Phone Agent API is running."}

@app.post(path="/voice")
async def handle_voice_call(request: Request):
    """
    Twilio webhook endpoint for incoming calls.

    When someone calls your Twilio number, Twilio sends a request here.
    We need to respond with TwiML (Twilio Markup Language) instructions.
    """

    # For now, just answer with a simple greeting
    twiml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Hello! Welcome to Luigi's Italian Restaurant. 
        This is your AI assistant. How can I help you today?
    </Say>
    <Pause length="2"/>
    <Say voice="Polly.Joanna">
        I'm still learning, but I'll be able to take reservations soon!
    </Say>
</Response>"""

    return Response(content=twiml_response,  media_type="application/xml")

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)