"""
Main FastAPI application for phone agent
Handles incoming calls from Twilio with Claude AI
"""

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
import os
from dotenv import load_dotenv

# Import our LLM service
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services.llm import llm_service

load_dotenv()

# Create FastAPI app
app = FastAPI(title="Phone Agent API", version="2.1.0")

# In-memory conversation storage (temporary - will improve later)
conversations = {}


@app.get("/")
async def read_root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "phone-agent",
        "message": "Phone Agent API with Claude AI",
        "version": "2.1.0 - Claude Integration"
    }


@app.post(path="/voice")
async def handle_voice_call(request: Request):
    """
    Twilio webhook endpoint for incoming calls.

    When someone calls, we greet them and gather their speech input.
    """

    # Get call SID to track conversation
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")

    # Initialize conversation for this call
    conversations[call_sid] = []

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
    Process the speech input using Claude AI.

    Twilio sends the transcribed text here, we ask Claude for a response.
    """
    # Get form data from Twilio
    form_data = await request.form()

    # Get the transcribed speech
    user_speech = form_data.get("SpeechResult", "")
    call_sid = form_data.get("CallSid", "unknown")
    confidence = form_data.get("Confidence", "0")

    print(f"[{call_sid}] User said: {user_speech} (confidence: {confidence})")

    # Get conversation history for this call
    conversation = conversations.get(call_sid, [])

    # Add user message to conversation
    conversation.append({
        "role": "user",
        "content": user_speech
    })

    # Get Claude's response
    try:
        ai_response = llm_service.get_response(user_speech, conversation)
        print(f"[{call_sid}] Claude responded: {ai_response}")

        # Add Claude's response to conversation
        conversation.append({
            "role": "assistant",
            "content": ai_response
        })

        # Update conversation history
        conversations[call_sid] = conversation

    except Exception as e:
        print(f"Error getting AI response: {e}")
        ai_response = "I'm sorry, I'm having trouble right now. Please call back later."

    # Continue gathering speech or end call
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/process-speech" method="POST" timeout="3" speechTimeout="auto">
        <Say voice="Polly.Joanna">{ai_response}</Say>
    </Gather>
    <Say voice="Polly.Joanna">Thank you for calling Luigi's! Goodbye!</Say>
</Response>"""

    return Response(content=twiml_response, media_type="application/xml")


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "features": ["speech_recognition", "claude_ai", "voice_response"],
        "active_conversations": len(conversations)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)