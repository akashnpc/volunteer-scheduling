"""Settings, read from environment variables (and backend/.env when present)."""
import os

from dotenv import load_dotenv

load_dotenv()


def _normalise_db_url(url: str) -> str:
    # Supabase / Heroku-style URLs start with postgres:// or postgresql://;
    # SQLAlchemy needs to be told which driver to use.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalise_db_url(os.getenv("DATABASE_URL", "sqlite:///./local.db"))
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-never-use-in-production-0000")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
# Comma-separated list of allowed browser origins, e.g. https://my-app.vercel.app
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
# Optional regex for extra allowed origins, e.g. Vercel preview URLs: https://.*\.vercel\.app
CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX") or None
# All shift times are wall-clock times in this zone ("organisation time").
ORG_TIMEZONE = os.getenv("ORG_TIMEZONE", "UTC")
SEED_ON_STARTUP = os.getenv("SEED_ON_STARTUP", "false").lower() == "true"
SEED_PASSWORD = os.getenv("SEED_PASSWORD", "Demo1234!")
UNDERSTAFFED_WINDOW_DAYS = 3
