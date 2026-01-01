"""
Main FastAPI application for phone agent
Handles incoming calls from Twilio
"""

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
import os
from dotenv import load_dotenv

load_dotenv()

# Create FastAPI app
app = FastAPI(title="Phone Agent API", version="2.0.0")


@app.get("/")
async def read_root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "phone-agent",
        "message": "Phone Agent API is running.",
        "version": "2.0.0 - Speech Recognition"
    }


@app.post(path="/voice")
async def handle_voice_call(request: Request):
    """
    Twilio webhook endpoint for incoming calls.

    When someone calls, we greet them and gather their speech input.
    """

    # Greet and gather speech input
    twiml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/process-speech" method="POST" timeout="3" speechTimeout="auto">
        <Say voice="Polly.Joanna">
            Hello! Welcome to Luigi's Italian Restaurant. 
            This is your AI assistant. How can I help you today?
        </Say>
    </Gather>
    <Say voice="Polly.Joanna">I didn't hear anything. Goodbye!</Say>
</Response>"""

    return Response(content=twiml_response, media_type="application/xml")


@app.post(path="/process-speech")
async def process_speech(request: Request):
    """
    Process the speech input from Twilio.

    Twilio sends the transcribed text here.
    """
    # Get form data from Twilio
    form_data = await request.form()

    # Get the transcribed speech
    user_speech = form_data.get("SpeechResult", "")
    confidence = form_data.get("Confidence", "0")

    print(f"User said: {user_speech} (confidence: {confidence})")

    # For now, just echo back what they said
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">
        You said: {user_speech}. Let me think about that.
    </Say>
    <Pause length="1"/>
    <Say voice="Polly.Joanna">
        I'm connecting to my AI brain to help you better. This is exciting!
    </Say>
</Response>"""

    return Response(content=twiml_response, media_type="application/xml")


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "features": ["speech_recognition", "voice_response"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)