"""
Main FastAPI application for phone agent
Full production version with Claude AI, database, and tool calling
"""

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Import our LLM service
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services.llm import llm_service
from services.database import init_db, get_db
from agent.tools.reservation_tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS

load_dotenv()

# Initialize database
init_db()

# Create FastAPI app
app = FastAPI(title="Phone Agent API", version="3.0.0")

# Mount static files directory for serving audio files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
    os.makedirs(os.path.join(static_dir, "sounds"))

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# In-memory conversation storage
conversations = {}


def parse_date_time(date_str: str, time_str: str) -> tuple:
    """
    Parse natural language date/time to standard format

    Returns:
        (date_YYYY-MM-DD, time_HH:MM)
    """
    # Handle common date formats
    today = datetime.now()

    date_lower = date_str.lower()
    if 'today' in date_lower:
        date = today.strftime("%Y-%m-%d")
    elif 'tomorrow' in date_lower:
        date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        # Try to parse as-is (assume already in correct format)
        date = date_str

    # Handle time formats (convert 12-hour to 24-hour)
    time_lower = time_str.lower().replace(' ', '')

    if 'pm' in time_lower and '12' not in time_lower:
        # Convert PM to 24-hour (except 12pm)
        hour = int(time_lower.split(':')[0] if ':' in time_lower else time_lower.replace('pm', ''))
        minute = int(time_lower.split(':')[1].replace('pm', '')) if ':' in time_lower else 0
        time = f"{hour + 12:02d}:{minute:02d}"
    elif 'am' in time_lower:
        hour = int(time_lower.split(':')[0] if ':' in time_lower else time_lower.replace('am', ''))
        minute = int(time_lower.split(':')[1].replace('am', '')) if ':' in time_lower else 0
        time = f"{hour:02d}:{minute:02d}"
    else:
        time = time_str

    return date, time


@app.get("/")
async def read_root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "phone-agent",
        "message": "Luigi's Restaurant AI Phone Agent - Production",
        "version": "3.0.0 - Full Database & Tools",
        "features": ["speech_recognition", "claude_ai", "function_calling", "database", "reservations"]
    }


@app.post(path="/voice")
async def handle_voice_call(request: Request):
    """Initial call handler - greet and start conversation"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")

    # Initialize conversation for this call
    conversations[call_sid] = {
        "messages": [],
        "tool_results": []
    }

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
    Process speech with Claude AI and tool calling
    This is where the magic happens!
    """
    # Get form data from Twilio
    form_data = await request.form()

    # Get the transcribed speech
    user_speech = form_data.get("SpeechResult", "")
    call_sid = form_data.get("CallSid", "unknown")
    caller_phone = form_data.get("From", "")

    print(f"\n[{call_sid}] User said: {user_speech}")

    # Get conversation history
    conv = conversations.get(call_sid, {"messages": [], "tool_results": []})
    messages = conv["messages"]

    # Add user message
    messages.append({
        "role": "user",
        "content": user_speech
    })

    # Call Claude with tools - this is the INDUSTRY PATTERN
    response = llm_service.get_response_with_tools(
        user_speech,
        conversation_history=messages,
        tools=TOOL_DEFINITIONS
    )

    print(f"[{call_sid}] Claude stop_reason: {response['stop_reason']}")

    # Process response
    assistant_text = ""
    tool_calls_made = []

    for block in response["content"]:
        if block["type"] == "text":
            assistant_text = block["text"]
            print(f"[{call_sid}] Claude said: {assistant_text}")

        elif block["type"] == "tool_use":
            # Claude wants to use a tool!
            tool_name = block["name"]
            tool_input = block["input"]
            tool_id = block["id"]

            print(f"[{call_sid}] Claude calling tool: {tool_name} with {tool_input}")

            # Execute the actual function
            try:
                # Get the function
                func = TOOL_FUNCTIONS[tool_name]

                # Call it with the parameters Claude provided
                if tool_name == "create_reservation":
                    # Add phone and call_sid to create_reservation
                    tool_input["phone"] = caller_phone
                    tool_input["call_sid"] = call_sid

                result = func(**tool_input)
                print(f"[{call_sid}] Tool result: {result}")

                # Add tool result to conversation
                messages.append({
                    "role": "assistant",
                    "content": response["content"]  # Include the tool use
                })

                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps(result)
                    }]
                })

                # Get Claude's response to the tool result
                followup = llm_service.get_response_with_tools(
                    "",  # No new user message
                    conversation_history=messages,
                    tools=TOOL_DEFINITIONS
                )

                # Extract text from followup
                for fb_block in followup["content"]:
                    if fb_block["type"] == "text":
                        assistant_text = fb_block["text"]
                        print(f"[{call_sid}] Claude (after tool): {assistant_text}")
                    elif fb_block["type"] == "tool_use":
                        # Claude wants to call ANOTHER tool (chaining)
                        # This happens when get_current_date → check_availability
                        print(f"[{call_sid}] Claude chaining to another tool: {fb_block['name']}")

                        # Execute the chained tool
                        chained_func = TOOL_FUNCTIONS[fb_block["name"]]
                        chained_input = fb_block["input"]

                        if fb_block["name"] == "create_reservation":
                            chained_input["phone"] = caller_phone
                            chained_input["call_sid"] = call_sid

                        chained_result = chained_func(**chained_input)
                        print(f"[{call_sid}] Chained tool result: {chained_result}")

                        # Add chained tool use to conversation
                        messages.append({
                            "role": "assistant",
                            "content": followup["content"]
                        })

                        messages.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": fb_block["id"],
                                "content": json.dumps(chained_result)
                            }]
                        })

                        # Get Claude's final response after chained tool
                        final_response = llm_service.get_response_with_tools(
                            "",
                            conversation_history=messages,
                            tools=TOOL_DEFINITIONS
                        )

                        # Extract final text
                        for final_block in final_response["content"]:
                            if final_block["type"] == "text":
                                assistant_text = final_block["text"]
                                print(f"[{call_sid}] Claude (final): {assistant_text}")

            except Exception as e:
                print(f"[{call_sid}] Error executing tool: {e}")
                assistant_text = "I'm sorry, I had trouble with that. Could you try again?"

    # Add assistant response to conversation
    if assistant_text and response["stop_reason"] != "tool_use":
        messages.append({
            "role": "assistant",
            "content": assistant_text
        })

    # Update conversation
    conversations[call_sid] = {
        "messages": messages,
        "tool_results": conv["tool_results"]
    }

    # Continue gathering or end call
    # The typing sound plays after Claude speaks, before listening again
    # Using our custom keyboard typing sound

    # Get the base URL for the request to construct full static file URL
    base_url = str(request.base_url).rstrip('/')
    typing_sound_url = f"{base_url}/static/sounds/writing-on-a-laptop-keyboard.wav"

    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{assistant_text}</Say>
    <Gather input="speech" action="/process-speech" method="POST" timeout="3" speechTimeout="auto">
        <Play>{typing_sound_url}</Play>
    </Gather>
    <Say voice="Polly.Joanna">Thank you for calling Luigi's! Goodbye!</Say>
</Response>"""

    return Response(content=twiml_response, media_type="application/xml")


@app.get("/health")
async def health_check():
    """Health check with database status"""
    db = get_db()
    try:
        from services.database import Reservation
        reservation_count = db.query(Reservation).count()
        db_status = "healthy"
    except Exception as e:
        reservation_count = 0
        db_status = f"error: {str(e)}"
    finally:
        db.close()

    return {
        "status": "healthy",
        "features": ["speech_recognition", "claude_ai", "function_calling", "database"],
        "active_conversations": len(conversations),
        "total_reservations": reservation_count,
        "database": db_status
    }


@app.get("/reservations")
async def list_reservations():
    """View all reservations (for debugging)"""
    from agent.tools.reservation_tools import get_reservations
    return {"reservations": get_reservations()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)