"""
Database models and setup for phone agent
Using SQLite (easy to upgrade to PostgreSQL later)
"""
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Create base class for models
Base = declarative_base()


class Reservation(Base):
    """Restaurant reservation model"""
    __tablename__ = 'reservations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20))
    party_size = Column(Integer, nullable=False)
    date = Column(String(20), nullable=False)  # YYYY-MM-DD format
    time = Column(String(10), nullable=False)  # HH:MM format (24-hour)
    status = Column(String(20), default='confirmed')  # confirmed, cancelled, completed
    assigned_table_id = Column(Integer)  # Which specific table is assigned
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    call_sid = Column(String(100))  # Twilio call ID

    def __repr__(self):
        return f"<Reservation(name={self.name}, party_size={self.party_size}, date={self.date}, time={self.time})>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'party_size': self.party_size,
            'date': self.date,
            'time': self.time,
            'status': self.status,
            'assigned_table_id': self.assigned_table_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Table(Base):
    """Restaurant table model"""
    __tablename__ = 'tables'

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_number = Column(Integer, unique=True, nullable=False)
    capacity = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Table(number={self.table_number}, capacity={self.capacity})>"

    def to_dict(self):
        return {
            "id": self.id,
            "table_number": self.table_number,
            "capacity": self.capacity,
            "is_active": self.is_active
        }


# ====================  QUALITY METRICS MODELS ====================

class CallMetrics(Base):
    """
    Raw metrics - WHAT happened during the call
    These are OBJECTIVE FACTS that can be measured deterministically
    """
    __tablename__ = "call_metrics"

    # Primary Key
    call_sid = Column(String(100), primary_key=True, index=True)

    # Timing (OBJECTIVE)
    call_start = Column(DateTime)
    call_end = Column(DateTime)
    total_duration_sec = Column(Float)

    # Conversation Flow (OBJECTIVE - counted from transcript)
    user_turns = Column(Integer, default=0)
    agent_turns = Column(Integer, default=0)
    clarifications_needed = Column(Integer, default=0)  # "Sorry, could you repeat?"

    # Outcomes (OBJECTIVE - binary facts)
    booking_completed = Column(Boolean, default=False)
    intent_fulfilled = Column(Boolean, default=False)  # Did we solve their problem?
    user_hung_up_early = Column(Boolean, default=False)  # Red flag!

    # Technical (OBJECTIVE - system measurements)
    tools_called = Column(JSON)  # ["get_current_date", "check_availability"]
    total_latency_ms = Column(Float, default=0)  # Total time waiting for Claude
    api_errors = Column(Integer, default=0)

    # A/B Testing (OBJECTIVE - which variant was used)
    prompt_version = Column(String(50), default="v1_baseline")  # "v1_baseline" | "v2_friendly" | "v3_efficient"

    # Metadata
    caller_phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    quality = relationship("CallQuality", back_populates="metrics", uselist=False)
    turns = relationship("ConversationTurn", back_populates="call")

    def __repr__(self):
        return f"<CallMetrics(call_sid={self.call_sid}, duration={self.total_duration_sec}s)>"

    def to_dict(self):
        return {
            "call_sid": self.call_sid,
            "call_start": self.call_start.isoformat() if self.call_start else None,
            "call_end": self.call_end.isoformat() if self.call_end else None,
            "total_duration_sec": self.total_duration_sec,
            "user_turns": self.user_turns,
            "agent_turns": self.agent_turns,
            "clarifications_needed": self.clarifications_needed,
            "booking_completed": self.booking_completed,
            "intent_fulfilled": self.intent_fulfilled,
            "user_hung_up_early": self.user_hung_up_early,
            "tools_called": self.tools_called,
            "total_latency_ms": self.total_latency_ms,
            "api_errors": self.api_errors,
            "prompt_version": self.prompt_version,
            "caller_phone": self.caller_phone,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class CallQuality(Base):
    """
    Quality assessment - HOW GOOD was the call
    This is SUBJECTIVE ASSESSMENT - requires analysis
    """
    __tablename__ = "call_quality"

    # Foreign Key
    call_sid = Column(String(100), ForeignKey("call_metrics.call_sid"), primary_key=True)

    # 5 Dimension Scores (0-100 each)
    efficiency_score = Column(Float, default=0)      # Fast, direct, minimal turns
    accuracy_score = Column(Float, default=0)         # Got details right
    helpfulness_score = Column(Float, default=0)      # Solved user's problem
    naturalness_score = Column(Float, default=75)     # Conversation flow (default until AI analyzes)
    professionalism_score = Column(Float, default=75) # Appropriate tone (default until AI analyzes)

    # Overall Quality
    overall_score = Column(Float, default=0)  # Weighted composite
    quality_tier = Column(String(20))  # "Poor" | "Fair" | "Good" | "Great" | "Excellent"

    # Sentiment Analysis
    user_sentiment = Column(String(20))  # "satisfied" | "neutral" | "frustrated"

    # Detected Issues
    frustration_detected = Column(Boolean, default=False)

    # Analysis Metadata
    analyzed_at = Column(DateTime)
    analyzer_version = Column(String(10), default="v1.0")  # Track which scoring logic version

    # Relationship
    metrics = relationship("CallMetrics", back_populates="quality")

    def __repr__(self):
        return f"<CallQuality(call_sid={self.call_sid}, score={self.overall_score}, tier={self.quality_tier})>"

    def to_dict(self):
        return {
            "call_sid": self.call_sid,
            "efficiency_score": self.efficiency_score,
            "accuracy_score": self.accuracy_score,
            "helpfulness_score": self.helpfulness_score,
            "naturalness_score": self.naturalness_score,
            "professionalism_score": self.professionalism_score,
            "overall_score": self.overall_score,
            "quality_tier": self.quality_tier,
            "user_sentiment": self.user_sentiment,
            "frustration_detected": self.frustration_detected,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "analyzer_version": self.analyzer_version
        }


class ConversationTurn(Base):
    """
    Individual turns - for deep analysis and debugging
    Stores the full conversation transcript
    """
    __tablename__ = "conversation_turns"

    id = Column(Integer, primary_key=True, index=True)
    call_sid = Column(String(100), ForeignKey("call_metrics.call_sid"), index=True)
    turn_number = Column(Integer)
    speaker = Column(String(10))  # "user" | "agent"
    transcript = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationship
    call = relationship("CallMetrics", back_populates="turns")

    def __repr__(self):
        return f"<ConversationTurn(call_sid={self.call_sid}, turn={self.turn_number}, speaker={self.speaker})>"

    def to_dict(self):
        return {
            "id": self.id,
            "call_sid": self.call_sid,
            "turn_number": self.turn_number,
            "speaker": self.speaker,
            "transcript": self.transcript,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


# ==================== DATABASE CONNECTION ====================

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./luigis_restaurant.db")
engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database and create tables"""
    # Create ALL tables
    Base.metadata.create_all(bind=engine)

    # Add some default tables if none exist
    session = SessionLocal()
    try:
        if session.query(Table).count() == 0:
            # Luigi's has 10 tables of various sizes
            tables = [
                Table(table_number=1, capacity=2),
                Table(table_number=2, capacity=2),
                Table(table_number=3, capacity=4),
                Table(table_number=4, capacity=4),
                Table(table_number=5, capacity=4),
                Table(table_number=6, capacity=6),
                Table(table_number=7, capacity=6),
                Table(table_number=8, capacity=8),
                Table(table_number=9, capacity=8),
                Table(table_number=10, capacity=10),
            ]
            session.add_all(tables)
            session.commit()
            print("✅ Created default tables")
    except Exception as e:
        print(f"Error initializing tables: {e}")
        session.rollback()
    finally:
        session.close()


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Don't close here, let caller handle it