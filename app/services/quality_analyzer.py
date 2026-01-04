"""
Quality Analyzer - Calculate quality scores for phone calls

This module implements the 5-dimensional quality scoring system:
1. Efficiency (algorithm-based)
2. Accuracy (algorithm-based)
3. Helpfulness (algorithm-based)
4. Naturalness (AI-based)
5. Professionalism (AI-based)
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple
import anthropic

from app.services.database import get_db, CallMetrics, CallQuality, ConversationTurn


# ==================== DIMENSION 1: EFFICIENCY (100% Algorithm) ====================

def calculate_efficiency_score(metrics: CallMetrics) -> float:
    """
    Calculate efficiency score based on objective metrics.
    Fast, direct conversations score higher.

    Ideal: 3-5 turns, under 2 minutes, no clarifications
    """
    score = 100.0

    # Penalty for too many turns (ideal: 3-5 user turns)
    if metrics.user_turns > 5:
        turn_penalty = (metrics.user_turns - 5) * 5
        score -= turn_penalty

    # Penalty for long duration (ideal: under 2 minutes = 120 seconds)
    if metrics.total_duration_sec and metrics.total_duration_sec > 120:
        duration_penalty = (metrics.total_duration_sec - 120) / 10
        score -= duration_penalty

    # Penalty for clarifications (asking user to repeat)
    clarification_penalty = metrics.clarifications_needed * 10
    score -= clarification_penalty

    # Penalty for high latency (ideal: under 3 seconds total)
    if metrics.total_latency_ms and metrics.total_latency_ms > 3000:
        latency_penalty = (metrics.total_latency_ms - 3000) / 100
        score -= latency_penalty

    return max(0.0, min(100.0, score))


# ==================== DIMENSION 2: ACCURACY (90% Algorithm) ====================

def calculate_accuracy_score(call_sid: str) -> float:
    """
    Calculate accuracy score by counting corrections and errors.
    Algorithm-based analysis of transcript.
    """
    db = get_db()
    try:
        # Get conversation turns
        turns = db.query(ConversationTurn).filter(
            ConversationTurn.call_sid == call_sid,
            ConversationTurn.speaker == "user"
        ).all()

        if not turns:
            return 75.0  # Default if no transcript

        score = 100.0

        # Count correction keywords in user messages
        correction_keywords = [
            "no", "actually", "i said", "that's wrong",
            "you mean", "not", "correction", "mistake",
            "i meant", "that's not right"
        ]

        corrections = 0
        for turn in turns:
            text = turn.transcript.lower()
            for keyword in correction_keywords:
                if keyword in text:
                    corrections += 1
                    break  # Only count once per turn

        # Penalty for corrections (-15 points each)
        score -= corrections * 15

        # Check for confirmations (bonus points)
        confirmation_keywords = [
            "yes that's right", "correct", "exactly",
            "yes", "perfect", "that's it"
        ]

        confirmations = 0
        for turn in turns:
            text = turn.transcript.lower()
            for keyword in confirmation_keywords:
                if keyword in text:
                    confirmations += 1
                    break

        # Bonus for confirmations (up to +20)
        score += min(confirmations * 5, 20)

        return max(0.0, min(100.0, score))

    finally:
        db.close()


# ==================== DIMENSION 3: HELPFULNESS (100% Algorithm) ====================

def calculate_helpfulness_score(metrics: CallMetrics) -> float:
    """
    Calculate helpfulness score based on outcome.
    Simple binary logic: did we help or not?
    """
    # Success: booking completed
    if metrics.booking_completed:
        return 100.0

    # Complete failure: user hung up early
    if metrics.user_hung_up_early:
        return 0.0

    # Check if call was too short (likely didn't help)
    if metrics.total_duration_sec and metrics.total_duration_sec < 30:
        return 20.0

    # Partial help: answered questions but no booking
    if metrics.intent_fulfilled:
        return 60.0

    # Default: some help provided
    return 50.0


# ==================== DIMENSION 4: NATURALNESS (100% AI) ====================

def calculate_naturalness_score(call_sid: str) -> float:
    """
    Calculate naturalness score using Claude AI.
    Analyzes conversation flow and human-likeness.
    """
    db = get_db()
    try:
        # Get full transcript
        turns = db.query(ConversationTurn).filter(
            ConversationTurn.call_sid == call_sid
        ).order_by(ConversationTurn.turn_number).all()

        if not turns:
            return 75.0  # Default if no transcript

        # Build conversation text
        transcript = "\n".join([
            f"{turn.speaker.capitalize()}: {turn.transcript}"
            for turn in turns
        ])

        # Call Claude API for analysis
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("⚠️  No ANTHROPIC_API_KEY - using default naturalness score")
            return 75.0

        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""You are a conversation quality expert analyzing phone calls.

Rate this conversation for NATURALNESS (0-100):

{transcript}

Criteria:
1. Greeting appropriateness (5-20 words, friendly not overly formal)
2. Natural language (sounds human, not robotic or scripted)
3. Smooth topic transitions (not abrupt)
4. Appropriate pacing (not too fast or slow)
5. Natural acknowledgments (uses "great", "perfect", etc naturally)

Return ONLY a JSON object with this exact format:
{{"score": 85, "reasoning": "brief explanation"}}"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse JSON response
        result_text = response.content[0].text
        # Remove markdown code blocks if present
        result_text = result_text.replace("```json", "").replace("```", "").strip()
        result = json.loads(result_text)

        return float(result.get("score", 75.0))

    except Exception as e:
        print(f"⚠️  Error calculating naturalness: {e}")
        return 75.0  # Default on error
    finally:
        db.close()


# ==================== DIMENSION 5: PROFESSIONALISM (100% AI) ====================

def calculate_professionalism_score(call_sid: str) -> float:
    """
    Calculate professionalism score using Claude AI.
    Analyzes tone and appropriateness.
    """
    db = get_db()
    try:
        # Get full transcript
        turns = db.query(ConversationTurn).filter(
            ConversationTurn.call_sid == call_sid
        ).order_by(ConversationTurn.turn_number).all()

        if not turns:
            return 75.0  # Default if no transcript

        # Build conversation text
        transcript = "\n".join([
            f"{turn.speaker.capitalize()}: {turn.transcript}"
            for turn in turns
        ])

        # Call Claude API for analysis
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("⚠️  No ANTHROPIC_API_KEY - using default professionalism score")
            return 75.0

        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""You are a conversation quality expert analyzing phone calls.

Rate this conversation for PROFESSIONALISM (0-100):

{transcript}

Criteria:
1. Courteous language (uses "please", "thank you", not demanding)
2. Appropriate formality (not too casual, not too stiff)
3. Clear communication (complete sentences, good grammar)
4. Handles issues gracefully (stays calm, doesn't blame)
5. No slang or inappropriate language

Return ONLY a JSON object with this exact format:
{{"score": 90, "reasoning": "brief explanation"}}"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse JSON response
        result_text = response.content[0].text
        # Remove markdown code blocks if present
        result_text = result_text.replace("```json", "").replace("```", "").strip()
        result = json.loads(result_text)

        return float(result.get("score", 75.0))

    except Exception as e:
        print(f"⚠️  Error calculating professionalism: {e}")
        return 75.0  # Default on error
    finally:
        db.close()


# ==================== OVERALL SCORE (Weighted Composite) ====================

def calculate_overall_score(dimensions: Dict[str, float]) -> Tuple[float, str]:
    """
    Calculate overall quality score and tier.

    Args:
        dimensions: Dict with keys: efficiency, accuracy, helpfulness, naturalness, professionalism

    Returns:
        Tuple of (overall_score, quality_tier)
    """
    # Weights (must sum to 1.0)
    weights = {
        "accuracy": 0.30,       # 30% - Most important (getting details right)
        "helpfulness": 0.25,    # 25% - Very important (solving problem)
        "efficiency": 0.20,     # 20% - Nice to have (being fast)
        "naturalness": 0.15,    # 15% - UX polish (sounding human)
        "professionalism": 0.10 # 10% - Baseline expected (being polite)
    }

    # Calculate weighted sum
    overall = sum(dimensions[k] * weights[k] for k in weights)

    # Determine quality tier
    if overall >= 90:
        tier = "Excellent"  # 🌟 Reference quality
    elif overall >= 75:
        tier = "Great"      # ✅ Target quality
    elif overall >= 60:
        tier = "Good"       # 👍 Acceptable
    elif overall >= 40:
        tier = "Fair"       # ⚠️  Needs improvement
    else:
        tier = "Poor"       # 🔴 Critical issue

    return overall, tier


# ==================== MAIN ANALYZER FUNCTION ====================

def analyze_call_quality(call_sid: str, use_ai: bool = True) -> Dict:
    """
    Analyze call quality across all 5 dimensions.

    Args:
        call_sid: Twilio call SID
        use_ai: Whether to use AI for naturalness/professionalism (default True)

    Returns:
        Dict with all quality scores and metadata
    """
    db = get_db()
    try:
        # Get call metrics
        metrics = db.query(CallMetrics).filter(CallMetrics.call_sid == call_sid).first()

        if not metrics:
            raise ValueError(f"No metrics found for call_sid: {call_sid}")

        # Calculate 5 dimensions
        efficiency = calculate_efficiency_score(metrics)
        accuracy = calculate_accuracy_score(call_sid)
        helpfulness = calculate_helpfulness_score(metrics)

        # AI-based dimensions (can be skipped for speed/cost)
        if use_ai:
            naturalness = calculate_naturalness_score(call_sid)
            professionalism = calculate_professionalism_score(call_sid)
        else:
            naturalness = 75.0  # Default
            professionalism = 75.0  # Default

        # Calculate overall
        dimensions = {
            "efficiency": efficiency,
            "accuracy": accuracy,
            "helpfulness": helpfulness,
            "naturalness": naturalness,
            "professionalism": professionalism
        }

        overall, tier = calculate_overall_score(dimensions)

        # Save to database
        quality = db.query(CallQuality).filter(CallQuality.call_sid == call_sid).first()

        if quality:
            # Update existing
            quality.efficiency_score = efficiency
            quality.accuracy_score = accuracy
            quality.helpfulness_score = helpfulness
            quality.naturalness_score = naturalness
            quality.professionalism_score = professionalism
            quality.overall_score = overall
            quality.quality_tier = tier
            quality.analyzed_at = datetime.utcnow()
        else:
            # Create new
            quality = CallQuality(
                call_sid=call_sid,
                efficiency_score=efficiency,
                accuracy_score=accuracy,
                helpfulness_score=helpfulness,
                naturalness_score=naturalness,
                professionalism_score=professionalism,
                overall_score=overall,
                quality_tier=tier,
                analyzed_at=datetime.utcnow()
            )
            db.add(quality)

        db.commit()

        return {
            "call_sid": call_sid,
            "dimensions": dimensions,
            "overall_score": overall,
            "quality_tier": tier,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


# ==================== BATCH ANALYSIS ====================

def analyze_pending_calls(limit: int = 20) -> List[Dict]:
    """
    Analyze calls that haven't been analyzed yet (batch processing).

    Args:
        limit: Maximum number of calls to analyze

    Returns:
        List of analysis results
    """
    db = get_db()
    try:
        # Find calls without quality analysis or with default AI scores
        pending = db.query(CallMetrics).outerjoin(CallQuality).filter(
            (CallQuality.call_sid == None) |  # No quality record
            (CallQuality.naturalness_score == 75.0)  # Default value, needs AI
        ).limit(limit).all()

        results = []
        for metrics in pending:
            try:
                result = analyze_call_quality(metrics.call_sid, use_ai=True)
                results.append(result)
                print(f"✅ Analyzed {metrics.call_sid}: {result['quality_tier']} ({result['overall_score']:.1f})")
            except Exception as e:
                print(f"❌ Error analyzing {metrics.call_sid}: {e}")

        return results

    finally:
        db.close()