import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    PLACES_API_KEY: str = os.getenv("PLACES_API_KEY")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")
    # Signing key for auth tokens. Override in production via the environment;
    # the fallback only keeps local development from crashing.
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-only-insecure-change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = int(os.getenv("JWT_EXPIRE_DAYS", "7"))

settings = Settings()