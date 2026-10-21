from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.database import Base
import uuid

class User(Base):
    __tablename__ = "users"
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    # bcrypt hash; nullable so the legacy demo account (no password) still works.
    password_hash = Column(String, nullable=True)
    default_transport_mode = Column(String)
    dietary_preferences = Column(JSONB)
    preferences = Column(JSONB) # NEW: For future LLM personalization