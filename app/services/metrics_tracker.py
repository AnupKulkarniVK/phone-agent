"""
Metrics Tracker - Track call metrics during phone conversations
Integrates with main.py to collect quality metrics in real-time
"""
from datetime import datetime
from typing import Dict, List, Optional
from app.services.database import get_db, CallMetrics, ConversationTurn
from app.services.quality_analyzer import analyze_call_quality


class CallMetricsTracker:
    """
    Tracks metrics for a single phone call.
    Use this in main.py to collect data during the conversation.
    """

    def __init__(self, call_sid: str, caller_phone: str = None):
        self.call_sid = call_sid
        self.caller_phone = caller_phone
        self.call_start = datetime.utcnow()
        self.call_end = None

        # Conversation tracking
        self.user_turns = 0
        self.agent_turns = 0
        self.clarifications_needed = 0
        self.conversation_turns = []  # List of (speaker, text, timestamp)

        # Outcomes
        self.booking_completed = False
        self.intent_fulfilled = False
        self.user_hung_up_early = False

        # Technical metrics
        self.tools_called = []
        self.total_latency_ms = 0.0
        self.api_errors = 0

        # A/B testing
        self.prompt_version = "v1_baseline"  # Default, can override

    def add_user_turn(self, text: str):
        """Record a user message"""
        self.user_turns += 1
        timestamp = datetime.utcnow()
        self.conversation_turns.append(("user", text, timestamp))

        # Detect clarification requests
        clarification_phrases = [
            "sorry", "pardon", "what", "repeat", "didn't catch",
            "can you say", "speak up", "come again"
        ]
        if any(phrase in text.lower() for phrase in clarification_phrases):
            self.clarifications_needed += 1

    def add_agent_turn(self, text: str):
        """Record an agent message"""
        self.agent_turns += 1
        timestamp = datetime.utcnow()
        self.conversation_turns.append(("agent", text, timestamp))

    def add_tool_call(self, tool_name: str, latency_ms: float = 0):
        """Record a tool being called"""
        self.tools_called.append(tool_name)
        self.total_latency_ms += latency_ms

    def add_api_error(self):
        """Record an API error"""
        self.api_errors += 1

    def set_booking_completed(self, completed: bool):
        """Mark if booking was completed"""
        self.booking_completed = completed
        if completed:
            self.intent_fulfilled = True

    def set_user_hung_up_early(self, hung_up: bool):
        """Mark if user hung up before completion"""
        self.user_hung_up_early = hung_up

    def finalize_call(self) -> str:
        """
        Call this when the phone call ends.
        Saves all metrics to database and triggers quality analysis.

        Returns:
            call_sid
        """
        self.call_end = datetime.utcnow()

        db = get_db()
        try:
            # Calculate duration
            duration = (self.call_end - self.call_start).total_seconds()

            # Save CallMetrics
            metrics = CallMetrics(
                call_sid=self.call_sid,
                call_start=self.call_start,
                call_end=self.call_end,
                total_duration_sec=duration,
                user_turns=self.user_turns,
                agent_turns=self.agent_turns,
                clarifications_needed=self.clarifications_needed,
                booking_completed=self.booking_completed,
                intent_fulfilled=self.intent_fulfilled,
                user_hung_up_early=self.user_hung_up_early,
                tools_called=self.tools_called,
                total_latency_ms=self.total_latency_ms,
                api_errors=self.api_errors,
                prompt_version=self.prompt_version,
                caller_phone=self.caller_phone
            )
            db.add(metrics)

            # Save ConversationTurns
            for turn_num, (speaker, text, timestamp) in enumerate(self.conversation_turns, 1):
                turn = ConversationTurn(
                    call_sid=self.call_sid,
                    turn_number=turn_num,
                    speaker=speaker,
                    transcript=text,
                    timestamp=timestamp
                )
                db.add(turn)

            db.commit()

            print(f"✅ Saved metrics for call {self.call_sid}")
            print(f"   Duration: {duration:.1f}s, Turns: {self.user_turns}, Booking: {self.booking_completed}")

            # Run quick quality analysis (algorithm-based, no AI)
            try:
                result = analyze_call_quality(self.call_sid, use_ai=False)
                print(f"   Quality: {result['overall_score']:.1f}/100 ({result['quality_tier']})")
            except Exception as e:
                print(f"   ⚠️  Quality analysis will run later: {e}")

            return self.call_sid

        except Exception as e:
            db.rollback()
            print(f"❌ Error saving metrics: {e}")
            raise
        finally:
            db.close()

    def to_dict(self) -> Dict:
        """Get current metrics as dict (for debugging)"""
        return {
            "call_sid": self.call_sid,
            "duration_so_far": (datetime.utcnow() - self.call_start).total_seconds(),
            "user_turns": self.user_turns,
            "agent_turns": self.agent_turns,
            "clarifications_needed": self.clarifications_needed,
            "booking_completed": self.booking_completed,
            "tools_called": self.tools_called,
            "total_latency_ms": self.total_latency_ms
        }


# ==================== GLOBAL TRACKER STORAGE ====================

# Store active call trackers (in-memory for current calls)
active_trackers: Dict[str, CallMetricsTracker] = {}


def start_tracking_call(call_sid: str, caller_phone: str = None) -> CallMetricsTracker:
    """
    Start tracking a new call.
    Call this at the beginning of a phone conversation.
    """
    tracker = CallMetricsTracker(call_sid, caller_phone)
    active_trackers[call_sid] = tracker
    print(f"📊 Started tracking call: {call_sid}")
    return tracker


def get_tracker(call_sid: str) -> Optional[CallMetricsTracker]:
    """Get the tracker for an active call"""
    return active_trackers.get(call_sid)


def end_tracking_call(call_sid: str) -> str:
    """
    End tracking and save metrics.
    Call this when the phone call ends.
    """
    tracker = active_trackers.get(call_sid)
    if not tracker:
        print(f"⚠️  No tracker found for call {call_sid}")
        return call_sid

    # Finalize and save
    tracker.finalize_call()

    # Remove from active trackers
    del active_trackers[call_sid]

    return call_sid
