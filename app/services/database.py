"""
Database models and setup for phone agent
Using SQLite (easy to upgrade to PostgreSQL later)
"""
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

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


# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./luigis_restaurant.db")
engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database and create tables"""
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