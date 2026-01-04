"""
Test script for Quality Analyzer
Creates sample call data and tests scoring
"""
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.database import get_db, CallMetrics, CallQuality, ConversationTurn
from app.services.quality_analyzer import analyze_call_quality


def create_sample_call():
    """Create a sample call with metrics and transcript"""
    db = get_db()

    try:
        call_sid = "TEST_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        # Create call metrics
        metrics = CallMetrics(
            call_sid=call_sid,
            call_start=datetime.utcnow() - timedelta(minutes=2),
            call_end=datetime.utcnow(),
            total_duration_sec=87.0,
            user_turns=4,
            agent_turns=4,
            clarifications_needed=0,
            booking_completed=True,
            intent_fulfilled=True,
            user_hung_up_early=False,
            tools_called=["get_current_date", "check_availability", "create_reservation"],
            total_latency_ms=1800.0,
            api_errors=0,
            prompt_version="v1_baseline",
            caller_phone="+14085551234"
        )
        db.add(metrics)

        # Create conversation turns
        turns_data = [
            ("agent", "Hello! Welcome to Luigi's. How can I help you today?"),
            ("user", "I need a table for 4 people tomorrow at 7pm"),
            ("agent", "Great! Let me check availability for 4 people tomorrow at 7pm."),
            ("user", "Yes please"),
            ("agent", "Perfect! We have a table available. May I have your name?"),
            ("user", "John Smith"),
            ("agent", "Excellent! Your reservation is confirmed for John Smith, 4 people tomorrow at 7pm. See you then!"),
            ("user", "Thank you!")
        ]

        for i, (speaker, text) in enumerate(turns_data):
            turn = ConversationTurn(
                call_sid=call_sid,
                turn_number=i + 1,
                speaker=speaker,
                transcript=text,
                timestamp=datetime.utcnow() - timedelta(seconds=(len(turns_data) - i) * 10)
            )
            db.add(turn)

        db.commit()

        print(f"✅ Created sample call: {call_sid}")
        print(f"   Duration: {metrics.total_duration_sec}s")
        print(f"   Turns: {metrics.user_turns} user, {metrics.agent_turns} agent")
        print(f"   Booking: {'✅ Yes' if metrics.booking_completed else '❌ No'}")
        print("")

        return call_sid

    except Exception as e:
        db.rollback()
        print(f"❌ Error creating sample call: {e}")
        raise
    finally:
        db.close()


def test_quality_analyzer(call_sid: str):
    """Test quality analyzer on a call"""
    print("🧪 Testing Quality Analyzer...")
    print("")

    try:
        # Analyze without AI (fast)
        print("1️⃣  Running algorithm-based analysis (fast)...")
        result = analyze_call_quality(call_sid, use_ai=False)

        print(f"   Efficiency: {result['dimensions']['efficiency']:.1f}/100")
        print(f"   Accuracy: {result['dimensions']['accuracy']:.1f}/100")
        print(f"   Helpfulness: {result['dimensions']['helpfulness']:.1f}/100")
        print(f"   Naturalness: {result['dimensions']['naturalness']:.1f}/100 (default)")
        print(f"   Professionalism: {result['dimensions']['professionalism']:.1f}/100 (default)")
        print(f"   Overall: {result['overall_score']:.1f}/100 ({result['quality_tier']})")
        print("")

        # Analyze with AI (slow, costs money)
        user_input = input("Run AI analysis? (costs ~$0.01, takes 5 sec) [y/N]: ")
        if user_input.lower() == 'y':
            print("")
            print("2️⃣  Running AI analysis (slow, uses Claude API)...")
            result = analyze_call_quality(call_sid, use_ai=True)

            print(f"   Efficiency: {result['dimensions']['efficiency']:.1f}/100")
            print(f"   Accuracy: {result['dimensions']['accuracy']:.1f}/100")
            print(f"   Helpfulness: {result['dimensions']['helpfulness']:.1f}/100")
            print(f"   Naturalness: {result['dimensions']['naturalness']:.1f}/100 (AI)")
            print(f"   Professionalism: {result['dimensions']['professionalism']:.1f}/100 (AI)")
            print(f"   Overall: {result['overall_score']:.1f}/100 ({result['quality_tier']})")
            print("")

        print("✅ Quality analyzer working correctly!")
        print("")
        print("📊 Quality scores saved to database")
        print("   View with: SELECT * FROM call_quality WHERE call_sid = '{}'".format(call_sid))

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print("QUALITY ANALYZER TEST")
    print("=" * 60)
    print("")

    # Create sample call
    call_sid = create_sample_call()

    # Test analyzer
    test_quality_analyzer(call_sid)

    print("")
    print("=" * 60)
    print("Test complete!")
