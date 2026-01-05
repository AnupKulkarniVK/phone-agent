"""
Main FastAPI application for phone agent
Full production version with Claude AI, database, and tool calling
"""
from app.services.metrics_tracker import start_tracking_call, get_tracker, end_tracking_call
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
import os
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Import our LLM service
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services.llm import llm_service
from services.database import init_db, get_db
from agent.tools.reservation_tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy import func

import math
load_dotenv()

# Initialize database
init_db()

# Create FastAPI app
app = FastAPI(title="Phone Agent API", version="3.0.0")

# Setup templates for dashboard
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
if not os.path.exists(templates_dir):
    os.makedirs(templates_dir)

templates = Jinja2Templates(directory=templates_dir)


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
    from_number = form_data.get("From")
    start_tracking_call(call_sid, from_number)

    # Initialize conversation for this call
    conversations[call_sid] = {
        "messages": [],
        "tool_results": []
    }

    # Initial greeting
    greeting = "Hello! Welcome to Luigi's Italian Restaurant. This is your AI assistant. How can I help you today?"

    # ✅ TRACK AGENT'S FIRST TURN
    tracker = get_tracker(call_sid)
    if tracker:
        tracker.add_agent_turn(greeting)

    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/process-speech" method="POST" timeout="3" speechTimeout="auto">
        <Say voice="Polly.Joanna">{greeting}</Say>
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

    # ✅ TRACK USER TURN
    tracker = get_tracker(call_sid)
    if tracker:
        tracker.add_user_turn(user_speech)

    # Get conversation history
    conv = conversations.get(call_sid, {"messages": [], "tool_results": []})
    messages = conv["messages"]

    # Add user message
    messages.append({
        "role": "user",
        "content": user_speech
    })

    # ✅ TRACK LATENCY: Start timer before Claude API call
    start_time = time.time()

    # Call Claude with tools - this is the INDUSTRY PATTERN
    try:
        response = llm_service.get_response_with_tools(
            user_speech,
            conversation_history=messages,
            tools=TOOL_DEFINITIONS
        )

        # ✅ TRACK LATENCY: Calculate time taken
        latency_ms = (time.time() - start_time) * 1000
        if tracker:
            tracker.total_latency_ms += latency_ms

    except Exception as e:
        # ✅ TRACK API ERROR
        if tracker:
            tracker.add_api_error()
        raise

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

            # ✅ TRACK TOOL CALL
            if tracker:
                tracker.add_tool_call(tool_name)

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

                # ✅ TRACK BOOKING COMPLETION
                if tool_name == "create_reservation" and result.get("success"):
                    if tracker:
                        tracker.set_booking_completed(True)

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

                # ✅ TRACK LATENCY: Start timer for followup
                followup_start = time.time()

                # Get Claude's response to the tool result
                followup = llm_service.get_response_with_tools(
                    "",  # No new user message
                    conversation_history=messages,
                    tools=TOOL_DEFINITIONS
                )

                # ✅ TRACK LATENCY: Add followup latency
                followup_latency = (time.time() - followup_start) * 1000
                if tracker:
                    tracker.total_latency_ms += followup_latency

                # Extract text from followup
                for fb_block in followup["content"]:
                    if fb_block["type"] == "text":
                        assistant_text = fb_block["text"]
                        print(f"[{call_sid}] Claude (after tool): {assistant_text}")

                    elif fb_block["type"] == "tool_use":
                        # Claude wants to call ANOTHER tool (chaining)
                        # This happens when get_current_date → check_availability
                        print(f"[{call_sid}] Claude chaining to another tool: {fb_block['name']}")

                        # ✅ TRACK CHAINED TOOL CALL
                        if tracker:
                            tracker.add_tool_call(fb_block["name"])

                        # Execute the chained tool
                        chained_func = TOOL_FUNCTIONS[fb_block["name"]]
                        chained_input = fb_block["input"]

                        if fb_block["name"] == "create_reservation":
                            chained_input["phone"] = caller_phone
                            chained_input["call_sid"] = call_sid

                        chained_result = chained_func(**chained_input)
                        print(f"[{call_sid}] Chained tool result: {chained_result}")

                        # ✅ TRACK CHAINED BOOKING
                        if fb_block["name"] == "create_reservation" and chained_result.get("success"):
                            if tracker:
                                tracker.set_booking_completed(True)

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

                        # ✅ TRACK LATENCY: Start timer for final response
                        final_start = time.time()

                        # Get Claude's final response after chained tool
                        final_response = llm_service.get_response_with_tools(
                            "",
                            conversation_history=messages,
                            tools=TOOL_DEFINITIONS
                        )

                        # ✅ TRACK LATENCY: Add final latency
                        final_latency = (time.time() - final_start) * 1000
                        if tracker:
                            tracker.total_latency_ms += final_latency

                        # Extract final text
                        for final_block in final_response["content"]:
                            if final_block["type"] == "text":
                                assistant_text = final_block["text"]
                                print(f"[{call_sid}] Claude (final): {assistant_text}")

            except Exception as e:
                print(f"[{call_sid}] Error executing tool: {e}")
                # ✅ TRACK ERROR
                if tracker:
                    tracker.add_api_error()
                assistant_text = "I'm sorry, I had trouble with that. Could you try again?"

    # ✅ TRACK AGENT RESPONSE
    if assistant_text:
        if tracker:
            tracker.add_agent_turn(assistant_text)

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


@app.post("/call-ended")
async def call_ended(request: Request):
    """
    Twilio webhook called when call completes.
    This is where we finalize and save all metrics.
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    call_status = form_data.get("CallStatus", "unknown")

    print(f"📞 Call ended: {call_sid} - Status: {call_status}")

    # ✅ END TRACKING AND SAVE METRICS
    end_tracking_call(call_sid)

    # Clean up conversation memory
    if call_sid in conversations:
        del conversations[call_sid]

    return {"status": "ok", "call_sid": call_sid}


@app.get("/health")
async def health_check():
    """Health check with database status"""
    db = get_db()
    try:
        from services.database import Reservation, CallMetrics
        reservation_count = db.query(Reservation).count()
        metrics_count = db.query(CallMetrics).count()
        db_status = "healthy"
    except Exception as e:
        reservation_count = 0
        metrics_count = 0
        db_status = f"error: {str(e)}"
    finally:
        db.close()

    return {
        "status": "healthy",
        "features": ["speech_recognition", "claude_ai", "function_calling", "database", "quality_metrics"],
        "active_conversations": len(conversations),
        "total_reservations": reservation_count,
        "total_calls_tracked": metrics_count,
        "database": db_status
    }

@app.get("/metrics")
async def list_metrics():
    """View all call metrics (for debugging)"""
    db = get_db()
    try:
        from services.database import CallMetrics, CallQuality

        # Get last 10 calls with quality scores
        calls = db.query(CallMetrics).order_by(CallMetrics.created_at.desc()).limit(10).all()

        results = []
        for call in calls:
            call_data = call.to_dict()
            if call.quality:
                call_data["quality"] = call.quality.to_dict()
            results.append(call_data)

        return {
            "total_calls": db.query(CallMetrics).count(),
            "recent_calls": results
        }
    finally:
        db.close()

@app.get("/reservations")
async def list_reservations():
    """View all reservations (for debugging)"""
    from agent.tools.reservation_tools import get_reservations
    return {"reservations": get_reservations()}

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Dashboard overview page"""
    from services.database import CallMetrics, CallQuality

    db = get_db()
    try:
        # Get summary stats
        total_calls = db.query(CallMetrics).count()

        # Calls today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        calls_today = db.query(CallMetrics).filter(CallMetrics.created_at >= today_start).count()

        # Booking rate
        bookings_completed = db.query(CallMetrics).filter(CallMetrics.booking_completed == True).count()
        booking_rate = (bookings_completed / total_calls * 100) if total_calls > 0 else 0

        # Average quality score
        avg_quality = db.query(func.avg(CallQuality.overall_score)).scalar() or 0

        # Quality distribution
        quality_tiers = db.query(
            CallQuality.quality_tier,
            func.count(CallQuality.quality_tier)
        ).group_by(CallQuality.quality_tier).all()

        tier_counts = {tier: count for tier, count in quality_tiers}

        # Recent calls
        recent_calls = db.query(CallMetrics).order_by(
            CallMetrics.created_at.desc()
        ).limit(10).all()

        return templates.TemplateResponse("dashboard_home.html", {
            "request": request,
            "total_calls": total_calls,
            "calls_today": calls_today,
            "booking_rate": round(booking_rate, 1),
            "avg_quality": round(avg_quality, 1),
            "tier_counts": tier_counts,
            "recent_calls": recent_calls
        })
    finally:
        db.close()


@app.get("/dashboard/quality", response_class=HTMLResponse)
async def dashboard_quality(request: Request):
    """Quality analysis deep dive"""
    from services.database import CallMetrics, CallQuality

    db = get_db()
    try:
        # Get all calls with quality scores
        calls_with_quality = db.query(CallMetrics).join(CallQuality).order_by(
            CallMetrics.created_at.desc()
        ).limit(100).all()

        # Calculate average scores per dimension
        avg_scores = db.query(
            func.avg(CallQuality.efficiency_score).label('efficiency'),
            func.avg(CallQuality.accuracy_score).label('accuracy'),
            func.avg(CallQuality.helpfulness_score).label('helpfulness'),
            func.avg(CallQuality.naturalness_score).label('naturalness'),
            func.avg(CallQuality.professionalism_score).label('professionalism')
        ).first()

        return templates.TemplateResponse("dashboard_quality.html", {
            "request": request,
            "calls": calls_with_quality,
            "avg_efficiency": round(avg_scores.efficiency or 0, 1),
            "avg_accuracy": round(avg_scores.accuracy or 0, 1),
            "avg_helpfulness": round(avg_scores.helpfulness or 0, 1),
            "avg_naturalness": round(avg_scores.naturalness or 0, 1),
            "avg_professionalism": round(avg_scores.professionalism or 0, 1)
        })
    finally:
        db.close()


@app.get("/dashboard/calls/{call_sid}", response_class=HTMLResponse)
async def dashboard_call_detail(request: Request, call_sid: str):
    """Detailed view of a single call"""
    from services.database import CallMetrics, ConversationTurn

    db = get_db()
    try:
        # Get call metrics
        call = db.query(CallMetrics).filter(CallMetrics.call_sid == call_sid).first()

        if not call:
            return HTMLResponse(content=f"<h1>Call {call_sid} not found</h1>", status_code=404)

        # Get conversation turns
        turns = db.query(ConversationTurn).filter(
            ConversationTurn.call_sid == call_sid
        ).order_by(ConversationTurn.turn_number).all()

        return templates.TemplateResponse("dashboard_call_detail.html", {
            "request": request,
            "call": call,
            "turns": turns
        })
    finally:
        db.close()


@app.get("/dashboard/api/metrics")
async def api_metrics():
    """JSON API for dashboard charts"""
    from services.database import CallMetrics

    db = get_db()
    try:
        # Last 7 days of calls
        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        calls = db.query(CallMetrics).filter(
            CallMetrics.created_at >= seven_days_ago
        ).order_by(CallMetrics.created_at).all()

        # Group by day
        daily_stats = {}
        for call in calls:
            day = call.created_at.strftime("%Y-%m-%d")
            if day not in daily_stats:
                daily_stats[day] = {
                    "calls": 0,
                    "bookings": 0,
                    "total_quality": 0,
                    "quality_count": 0
                }

            daily_stats[day]["calls"] += 1
            if call.booking_completed:
                daily_stats[day]["bookings"] += 1

            if call.quality:
                daily_stats[day]["total_quality"] += call.quality.overall_score
                daily_stats[day]["quality_count"] += 1

        # Format for Chart.js
        labels = []
        calls_data = []
        booking_rate_data = []
        quality_data = []

        for day in sorted(daily_stats.keys()):
            stats = daily_stats[day]
            labels.append(day)
            calls_data.append(stats["calls"])

            booking_rate = (stats["bookings"] / stats["calls"] * 100) if stats["calls"] > 0 else 0
            booking_rate_data.append(round(booking_rate, 1))

            avg_quality = (stats["total_quality"] / stats["quality_count"]) if stats["quality_count"] > 0 else 0
            quality_data.append(round(avg_quality, 1))

        return {
            "labels": labels,
            "calls": calls_data,
            "booking_rate": booking_rate_data,
            "quality": quality_data
        }
    finally:
        db.close()

def calculate_t_statistic(sample1, sample2):
    """
    Calculate t-statistic between two samples.
    """
    n1 = len(sample1)
    n2 = len(sample2)

    if n1 < 2 or n2 < 2:
        return None, None

    # Calculate means
    mean1 = sum(sample1) / n1
    mean2 = sum(sample2) / n2

    # Calculate variances
    var1 = sum((x - mean1) ** 2 for x in sample1) / (n1 - 1)
    var2 = sum((x - mean2) ** 2 for x in sample2) / (n2 - 1)

    # Calculate pooled standard error
    pooled_se = math.sqrt(var1 / n1 + var2 / n2)

    if pooled_se == 0:
        return None, None

    # Calculate t-statistic
    t_stat = (mean1 - mean2) / pooled_se

    # Degrees of freedom (Welch-Satterthwaite equation)
    df = ((var1 / n1 + var2 / n2) ** 2) / (
            (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
    )

    # Simplified p-value estimation
    # For df > 30, use normal approximation
    if df > 30:
        # Using normal distribution approximation
        # |t| > 1.96 → p < 0.05 (95% confidence)
        # |t| > 2.58 → p < 0.01 (99% confidence)
        abs_t = abs(t_stat)
        if abs_t > 2.58:
            p_value = 0.01
        elif abs_t > 1.96:
            p_value = 0.05
        elif abs_t > 1.64:
            p_value = 0.10
        else:
            p_value = 0.20
    else:
        # Conservative estimate for smaller samples
        p_value = 0.10

    return t_stat, p_value

@app.get("/dashboard/ab-testing", response_class=HTMLResponse)
async def dashboard_ab_testing(request: Request):
    """A/B testing analysis dashboard"""
    from services.database import CallMetrics, CallQuality

    db = get_db()
    try:
        # Get all calls grouped by prompt version
        calls_by_variant = {}
        all_calls = db.query(CallMetrics).join(CallQuality).all()

        for call in all_calls:
            variant = call.prompt_version
            if variant not in calls_by_variant:
                calls_by_variant[variant] = []
            calls_by_variant[variant].append(call)

        # Define variant descriptions
        variant_info = {
            "v1_baseline": {
                "name": "v1_baseline",
                "description": "Standard professional greeting, formal tone"
            },
            "v2_friendly": {
                "name": "v2_friendly",
                "description": "Warm greeting, casual friendly tone"
            },
            "v3_efficient": {
                "name": "v3_efficient",
                "description": "Brief greeting, get straight to business"
            }
        }

        # Calculate stats for each variant
        variant_stats = []
        variant_chart_data = {
            "labels": [],
            "quality": [],
            "booking_rate": []
        }

        for variant, calls in calls_by_variant.items():
            if len(calls) == 0:
                continue

            # Calculate metrics
            call_count = len(calls)
            bookings = sum(1 for c in calls if c.booking_completed)
            booking_rate = (bookings / call_count * 100) if call_count > 0 else 0

            quality_scores = [c.quality.overall_score for c in calls if c.quality]
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

            efficiency_scores = [c.quality.efficiency_score for c in calls if c.quality]
            avg_efficiency = sum(efficiency_scores) / len(efficiency_scores) if efficiency_scores else 0

            accuracy_scores = [c.quality.accuracy_score for c in calls if c.quality]
            avg_accuracy = sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0

            naturalness_scores = [c.quality.naturalness_score for c in calls if c.quality]
            avg_naturalness = sum(naturalness_scores) / len(naturalness_scores) if naturalness_scores else 0

            professionalism_scores = [c.quality.professionalism_score for c in calls if c.quality]
            avg_professionalism = sum(professionalism_scores) / len(professionalism_scores) if professionalism_scores else 0

            helpfulness_scores = [c.quality.helpfulness_score for c in calls if c.quality]
            avg_helpfulness = sum(helpfulness_scores) / len(helpfulness_scores) if helpfulness_scores else 100

            variant_stats.append({
                "name": variant,
                "description": variant_info.get(variant, {}).get("description", "No description"),
                "call_count": call_count,
                "booking_rate": booking_rate,
                "avg_quality": avg_quality,
                "avg_efficiency": avg_efficiency,
                "avg_accuracy": avg_accuracy,
                "avg_naturalness": avg_naturalness,
                "avg_professionalism": avg_professionalism,
                "avg_helpfulness": avg_helpfulness,
                "quality_scores": quality_scores,
                "is_winner": False,
                "is_significant": False
            })

            # Add to chart data
            variant_chart_data["labels"].append(variant)
            variant_chart_data["quality"].append(round(avg_quality, 1))
            variant_chart_data["booking_rate"].append(round(booking_rate, 1))

        # Sort by quality score
        variant_stats.sort(key=lambda x: x["avg_quality"], reverse=True)

        # Determine statistical significance
        if len(variant_stats) >= 2:
            best_variant = variant_stats[0]
            best_scores = best_variant["quality_scores"]

            for variant in variant_stats[1:]:
                other_scores = variant["quality_scores"]

                # Need at least 30 samples for reliable t-test
                if len(best_scores) >= 30 and len(other_scores) >= 30:
                    t_stat, p_value = calculate_t_statistic(best_scores, other_scores)

                    # If p < 0.05, the difference is statistically significant
                    if p_value and p_value < 0.05:
                        variant["is_significant"] = True

            # Mark winner
            if len(best_variant["quality_scores"]) >= 30:
                best_variant["is_winner"] = True

        # Determine best variant
        best_variant_name = variant_stats[0]["name"] if variant_stats else "None"
        best_score = variant_stats[0]["avg_quality"] if variant_stats else 0

        # Prepare radar chart data
        colors = [
            ('rgba(102, 126, 234, 0.2)', '#667eea'),
            ('rgba(72, 187, 120, 0.2)', '#48bb78'),
            ('rgba(237, 137, 54, 0.2)', '#ed8936'),
        ]

        radar_chart_data = {"datasets": []}

        for i, variant in enumerate(variant_stats):
            color = colors[i % len(colors)]
            radar_chart_data["datasets"].append({
                "label": variant["name"],
                "data": [
                    round(variant["avg_efficiency"], 1),
                    round(variant["avg_accuracy"], 1),
                    round(variant["avg_helpfulness"], 1),
                    round(variant["avg_naturalness"], 1),
                    round(variant["avg_professionalism"], 1)
                ],
                "backgroundColor": color[0],
                "borderColor": color[1]
            })

        # Prepare time series data
        time_series_data = {"labels": [], "datasets": []}

        from datetime import datetime, timedelta
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)

        # Generate date labels
        current_date = start_date
        while current_date <= end_date:
            time_series_data["labels"].append(current_date.strftime("%m/%d"))
            current_date += timedelta(days=1)

        # Calculate daily averages for each variant
        for i, variant_name in enumerate(sorted(calls_by_variant.keys())):
            daily_scores = []
            current_date = start_date

            while current_date <= end_date:
                day_start = current_date.replace(hour=0, minute=0, second=0)
                day_end = current_date.replace(hour=23, minute=59, second=59)

                day_calls = [c for c in calls_by_variant[variant_name]
                             if day_start <= c.created_at <= day_end and c.quality]

                if day_calls:
                    avg_score = sum(c.quality.overall_score for c in day_calls) / len(day_calls)
                    daily_scores.append(round(avg_score, 1))
                else:
                    daily_scores.append(None)

                current_date += timedelta(days=1)

            color = colors[i % len(colors)]
            time_series_data["datasets"].append({
                "label": variant_name,
                "data": daily_scores,
                "borderColor": color[1],
                "backgroundColor": color[0]
            })

        # Generate recommendations
        recommendations = []

        if len(variant_stats) >= 2 and variant_stats[0]["call_count"] >= 30:
            best = variant_stats[0]
            worst = variant_stats[-1]

            quality_diff = best["avg_quality"] - worst["avg_quality"]

            if quality_diff > 10:
                recommendations.append({
                    "type": "success",
                    "title": f"Winner: {best['name']}",
                    "description": f"This variant outperforms {worst['name']} by {quality_diff:.1f} points. Consider making this the default."
                })

            if best["booking_rate"] > 95:
                recommendations.append({
                    "type": "success",
                    "title": "High Booking Rate",
                    "description": f"{best['name']} achieves {best['booking_rate']:.0f}% booking rate. Excellent conversion!"
                })

            # Check for trade-offs
            efficient_variant = max(variant_stats, key=lambda x: x["avg_efficiency"])
            natural_variant = max(variant_stats, key=lambda x: x["avg_naturalness"])

            if efficient_variant["name"] != natural_variant["name"]:
                recommendations.append({
                    "type": "info",
                    "title": "Trade-off Detected",
                    "description": f"{efficient_variant['name']} is most efficient, but {natural_variant['name']} sounds most natural. Consider your priority."
                })
        else:
            recommendations.append({
                "type": "warning",
                "title": "Insufficient Data",
                "description": "Need at least 30 calls per variant for reliable statistical analysis. Continue collecting data."
            })

        return templates.TemplateResponse("dashboard_ab_testing.html", {
            "request": request,
            "variants": list(calls_by_variant.keys()),
            "total_calls": len(all_calls),
            "best_variant": best_variant_name,
            "best_score": best_score,
            "variant_stats": variant_stats,
            "variant_chart_data": variant_chart_data,
            "radar_chart_data": radar_chart_data,
            "time_series_data": time_series_data,
            "recommendations": recommendations
        })
    finally:
        db.close()
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)