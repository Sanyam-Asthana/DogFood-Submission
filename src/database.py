import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from src.config import settings

logger = logging.getLogger(__name__)

# Configure database engine
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(
        db_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    # Verify connection
    with engine.connect() as conn:
        pass
    logger.info(f"Database connection established successfully ({db_url.split('@')[-1] if '@' in db_url else db_url}).")
except Exception as e:
    logger.warning(
        f"Failed to connect using DATABASE_URL={db_url}: {e}. "
        "Falling back to local SQLite database."
    )
    fallback_url = "sqlite:///./portal.db"
    engine = create_engine(
        fallback_url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency to yield a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all database tables and ensure RLS is enabled on PostgreSQL."""
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE events ADD COLUMN max_team_size INTEGER DEFAULT 4;"))
            conn.commit()
        except Exception:
            pass
    if "postgresql" in str(engine.url):
        try:
            with engine.connect() as conn:
                for table in ["events", "tracks", "users"]:
                    conn.execute(text(f"ALTER TABLE IF EXISTS {table} ENABLE ROW LEVEL SECURITY;"))
                    conn.execute(
                        text(
                            f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = '{table}' AND policyname = 'Public read {table}') THEN "
                            f"CREATE POLICY \"Public read {table}\" ON {table} FOR SELECT USING (true); END IF; END $$;"
                        )
                    )
                # Drop unique constraint on session_token if it exists, converting it to a standard index
                conn.execute(text("DROP INDEX IF EXISTS ix_users_session_token;"))
                conn.execute(text("ALTER TABLE IF EXISTS users DROP CONSTRAINT IF EXISTS ix_users_session_token;"))
                conn.execute(text("ALTER TABLE IF EXISTS users ALTER COLUMN session_token TYPE VARCHAR(255);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_session_token ON users (session_token);"))
                # Repair any duplicate sliced JWT session tokens
                conn.execute(text("UPDATE users SET session_token = 'usr_' || id WHERE session_token LIKE 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpX%';"))
                conn.commit()
            logger.info("Row Level Security (RLS) enabled on public tables and session_token constraint cleaned up.")
        except Exception as e:
            logger.warning(f"Could not auto-enable RLS: {e}")
