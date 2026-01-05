"""
Generate Synthetic Call Data for Dashboard Testing

This script creates realistic phone call data with:
- Different quality tiers (Excellent, Great, Good, Fair, Poor)
- Realistic conversation transcripts
- Varied outcomes (successful bookings, cancellations, hang-ups)
- Spread across the last 7 days

Run this to populate your dashboard with demo data!
"""
import sys
import os
from datetime import datetime, timedelta
import random

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.database import get_db, CallMetrics, CallQuality, ConversationTurn

num_calls = os.getenv("SYNTHETIC_CALLS")

# ==================== SYNTHETIC DATA TEMPLATES ====================

CALL_TEMPLATES = [
    # EXCELLENT CALLS (90-100)
    {
        "tier": "Excellent",
        "user_turns": 3,
        "agent_turns": 3,
        "duration": random.randint(45, 75),
        "clarifications": 0,
        "booking_completed": True,
        "tools": ["get_current_date", "check_availability", "create_reservation"],
        "conversation": [
            ("agent", "Hello! Welcome to Luigi's Italian Restaurant. How can I help you today?"),
            ("user", "I'd like to make a reservation for 4 people tomorrow at 7pm"),
            ("agent", "Perfect! Let me check availability for 4 people tomorrow at 7pm."),
            ("agent", "Great news! We have a table available. May I have your name?"),
            ("user", "Sarah Johnson"),
            ("agent", "Excellent! Your reservation is confirmed for Sarah Johnson, 4 people tomorrow at 7pm. See you then!"),
            ("user", "Thank you!")
        ],
        "scores": {
            "efficiency": random.uniform(88, 98),
            "accuracy": random.uniform(95, 100),
            "helpfulness": 100,
            "naturalness": random.uniform(85, 95),
            "professionalism": random.uniform(90, 98)
        }
    },

    # GREAT CALLS (75-89)
    {
        "tier": "Great",
        "user_turns": 4,
        "agent_turns": 4,
        "duration": random.randint(80, 120),
        "clarifications": 0,
        "booking_completed": True,
        "tools": ["get_current_date", "check_availability", "create_reservation"],
        "conversation": [
            ("agent", "Hello! Welcome to Luigi's. How can I help you?"),
            ("user", "Hi, I need a table for tomorrow"),
            ("agent", "Sure! How many people will be joining you?"),
            ("user", "Six people at around 6pm"),
            ("agent", "Let me check availability for 6 people tomorrow at 6pm."),
            ("agent", "Perfect! We have a table for you. Can I get your name?"),
            ("user", "Michael Chen"),
            ("agent", "All set! Reservation confirmed for Michael Chen, 6 people tomorrow at 6pm."),
            ("user", "Great, thanks!")
        ],
        "scores": {
            "efficiency": random.uniform(75, 87),
            "accuracy": random.uniform(88, 95),
            "helpfulness": 100,
            "naturalness": random.uniform(75, 85),
            "professionalism": random.uniform(82, 90)
        }
    },

    # GOOD CALLS (60-74)
    {
        "tier": "Good",
        "user_turns": 6,
        "agent_turns": 6,
        "duration": random.randint(120, 180),
        "clarifications": 1,
        "booking_completed": True,
        "tools": ["get_current_date", "check_availability", "create_reservation"],
        "conversation": [
            ("agent", "Hello! Welcome to Luigi's Italian Restaurant. How may I assist you today?"),
            ("user", "Um, I need a reservation"),
            ("agent", "I'd be happy to help! How many people and what date?"),
            ("user", "What?"),
            ("agent", "How many guests will be dining with you?"),
            ("user", "Oh, 4 people. Next Friday"),
            ("agent", "Great! What time works for you on Friday?"),
            ("user", "Maybe 8pm?"),
            ("agent", "Let me check 8pm for 4 people next Friday."),
            ("agent", "We have availability! May I have your name please?"),
            ("user", "Jessica Martinez"),
            ("agent", "Perfect! Confirmed for Jessica Martinez, 4 people Friday at 8pm."),
            ("user", "Okay, thanks")
        ],
        "scores": {
            "efficiency": random.uniform(55, 70),
            "accuracy": random.uniform(75, 88),
            "helpfulness": 100,
            "naturalness": random.uniform(65, 75),
            "professionalism": random.uniform(70, 80)
        }
    },

    # FAIR CALLS (40-59)
    {
        "tier": "Fair",
        "user_turns": 8,
        "agent_turns": 8,
        "duration": random.randint(180, 240),
        "clarifications": 3,
        "booking_completed": True,
        "tools": ["get_current_date", "check_availability", "check_availability", "create_reservation"],
        "conversation": [
            ("agent", "Good afternoon! Thank you for calling Luigi's Italian Restaurant. How may I help you?"),
            ("user", "I need to book something"),
            ("agent", "Certainly! Are you looking to make a dinner reservation?"),
            ("user", "Yeah"),
            ("agent", "Wonderful! How many guests?"),
            ("user", "Huh?"),
            ("agent", "How many people will be dining?"),
            ("user", "Two people"),
            ("agent", "Great! What day were you thinking?"),
            ("user", "This weekend maybe"),
            ("agent", "Saturday or Sunday?"),
            ("user", "Saturday night"),
            ("agent", "What time on Saturday?"),
            ("user", "I don't know, 7 or 8?"),
            ("agent", "Let me check both times. Would 7:30pm work?"),
            ("user", "Sure I guess"),
            ("agent", "May I have a name for the reservation?"),
            ("user", "David Lee")
        ],
        "scores": {
            "efficiency": random.uniform(35, 50),
            "accuracy": random.uniform(60, 75),
            "helpfulness": 100,
            "naturalness": random.uniform(50, 65),
            "professionalism": random.uniform(60, 70)
        }
    },

    # POOR CALLS (0-39)
    {
        "tier": "Poor",
        "user_turns": 5,
        "agent_turns": 5,
        "duration": random.randint(90, 150),
        "clarifications": 2,
        "booking_completed": False,
        "tools": ["check_availability"],
        "conversation": [
            ("agent", "Hello! Welcome to Luigi's Italian Restaurant establishment. How can I be of service today?"),
            ("user", "Do you have tables?"),
            ("agent", "Yes, we do have tables available. How many people?"),
            ("user", "What?"),
            ("agent", "I apologize. How many guests will be joining you?"),
            ("user", "4 people tomorrow"),
            ("agent", "Let me check our availability database system."),
            ("user", "This is taking forever"),
            ("agent", "I apologize for the delay. What time were you interested in?"),
            ("user", "*hangs up*")
        ],
        "scores": {
            "efficiency": random.uniform(15, 35),
            "accuracy": random.uniform(40, 60),
            "helpfulness": 0,
            "naturalness": random.uniform(30, 45),
            "professionalism": random.uniform(50, 65)
        }
    }
]


CALLER_NAMES = [
    "Emily Rodriguez", "James Wilson", "Sophia Patel", "Liam Anderson",
    "Olivia Kim", "Noah Garcia", "Emma Thompson", "William Zhang",
    "Ava Martinez", "Mason Brown", "Isabella Lee", "Ethan Davis",
    "Mia Johnson", "Alexander Wang", "Charlotte Taylor", "Daniel Moore",
    "Amelia Jackson", "Matthew White", "Harper Harris", "David Martin"
]


# ==================== DATA GENERATION FUNCTIONS ====================

def generate_call_sid():
    """Generate a realistic Twilio call SID"""
    import string
    chars = string.ascii_uppercase + string.digits
    return "CA" + ''.join(random.choices(chars, k=32))


def generate_phone_number():
    """Generate a realistic US phone number"""
    area_code = random.choice([408, 650, 415, 510, 925, 669])
    exchange = random.randint(200, 999)
    number = random.randint(1000, 9999)
    return f"+1{area_code}{exchange}{number}"


def calculate_overall_score(scores):
    """Calculate weighted overall score"""
    weights = {
        "accuracy": 0.30,
        "helpfulness": 0.25,
        "efficiency": 0.20,
        "naturalness": 0.15,
        "professionalism": 0.10
    }

    overall = (
            scores["efficiency"] * weights["efficiency"] +
            scores["accuracy"] * weights["accuracy"] +
            scores["helpfulness"] * weights["helpfulness"] +
            scores["naturalness"] * weights["naturalness"] +
            scores["professionalism"] * weights["professionalism"]
    )

    return overall


def get_quality_tier(score):
    """Map score to tier"""
    if score >= 90:
        return "Excellent"
    elif score >= 75:
        return "Great"
    elif score >= 60:
        return "Good"
    elif score >= 40:
        return "Fair"
    else:
        return "Poor"


def generate_synthetic_calls(num_calls=20):
    """Generate synthetic call data"""

    db = get_db()

    try:
        print(f"🎬 Generating {num_calls} synthetic calls...")
        print("")

        # Spread calls across last 7 days
        now = datetime.utcnow()

        for i in range(num_calls):
            # Pick a random template
            template = random.choice(CALL_TEMPLATES)

            # Generate timestamp (spread across 7 days, weighted toward recent)
            days_ago = random.choices(
                range(7),
                weights=[5, 5, 4, 3, 2, 1, 1],  # More recent calls weighted higher
                k=1
            )[0]
            hours_ago = random.randint(0, 23)
            minutes_ago = random.randint(0, 59)

            call_time = now - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)

            # Generate call data
            call_sid = generate_call_sid()
            caller_phone = generate_phone_number()
            caller_name = random.choice(CALLER_NAMES)
            duration = template["duration"] + random.uniform(-10, 10)

            # Calculate latency (realistic: 1-3 seconds per API call)
            num_tools = len(template["tools"])
            latency_ms = num_tools * random.uniform(1000, 3000)

            # Create CallMetrics
            metrics = CallMetrics(
                call_sid=call_sid,
                call_start=call_time,
                call_end=call_time + timedelta(seconds=duration),
                total_duration_sec=duration,
                user_turns=template["user_turns"],
                agent_turns=template["agent_turns"],
                clarifications_needed=template["clarifications"],
                booking_completed=template["booking_completed"],
                intent_fulfilled=template["booking_completed"],
                user_hung_up_early=not template["booking_completed"],
                tools_called=template["tools"],
                total_latency_ms=latency_ms,
                api_errors=0,
                prompt_version=random.choice(["v1_baseline", "v2_friendly", "v3_efficient"]),
                caller_phone=caller_phone,
                created_at=call_time
            )
            db.add(metrics)

            # Create ConversationTurns
            for turn_num, (speaker, text) in enumerate(template["conversation"], 1):
                turn = ConversationTurn(
                    call_sid=call_sid,
                    turn_number=turn_num,
                    speaker=speaker,
                    transcript=text.replace("Sarah Johnson", caller_name)
                    .replace("Michael Chen", caller_name)
                    .replace("Jessica Martinez", caller_name)
                    .replace("David Lee", caller_name),
                    timestamp=call_time + timedelta(seconds=turn_num * 10)
                )
                db.add(turn)

            # Create CallQuality
            scores = template["scores"].copy()
            overall_score = calculate_overall_score(scores)
            tier = get_quality_tier(overall_score)

            quality = CallQuality(
                call_sid=call_sid,
                efficiency_score=scores["efficiency"],
                accuracy_score=scores["accuracy"],
                helpfulness_score=scores["helpfulness"],
                naturalness_score=scores["naturalness"],
                professionalism_score=scores["professionalism"],
                overall_score=overall_score,
                quality_tier=tier,
                user_sentiment="satisfied" if template["booking_completed"] else "frustrated",
                frustration_detected=not template["booking_completed"],
                analyzed_at=call_time + timedelta(seconds=duration + 5),
                analyzer_version="v1.0"
            )
            db.add(quality)

            # Print progress
            tier_emoji = {
                "Excellent": "🌟",
                "Great": "✅",
                "Good": "👍",
                "Fair": "⚠️",
                "Poor": "🔴"
            }
            print(f"{tier_emoji.get(tier, '📞')} Call {i+1:2d}: {tier:10s} ({overall_score:.1f}/100) - {caller_name} - {days_ago}d ago")

        # Commit all data
        db.commit()

        print("")
        print("✅ Successfully generated synthetic call data!")
        print("")

        # Show summary
        tier_counts = db.query(
            CallQuality.quality_tier,
            func.count(CallQuality.quality_tier)
        ).group_by(CallQuality.quality_tier).all()

        print("📊 Quality Distribution:")
        for tier, count in tier_counts:
            print(f"   {tier}: {count} calls")

        print("")
        print(f"🎉 Dashboard is now populated with {num_calls} synthetic calls!")
        print(f"   Visit: https://phone-agent-9b99.onrender.com/dashboard")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


# ==================== MAIN ====================

if __name__ == "__main__":
    from sqlalchemy import func

    print("=" * 60)
    print("SYNTHETIC CALL DATA GENERATOR")
    print("=" * 60)
    print("")

    # Ask user how many calls
    try:
        num_calls = int(input("How many synthetic calls to generate? [20]: ") or "20")
    except ValueError:
        num_calls = 20

    print("")

    # Generate data
    generate_synthetic_calls(num_calls)

    print("")
    print("=" * 60)
