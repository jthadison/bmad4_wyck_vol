"""Initialize database schema."""
import asyncio
import sys

# Import all ORM models to register them with SQLAlchemy Base
import src.repositories.models  # noqa: F401
from src.database import init_db


async def main():
    """Run database initialization."""
    print("Initializing database schema...")
    try:
        await init_db()
        print("Database schema initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Use SelectorEventLoop on Windows for psycopg compatibility
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
