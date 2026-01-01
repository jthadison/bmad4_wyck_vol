"""Run Alembic migrations with Windows event loop fix."""
import asyncio
import subprocess
import sys

if __name__ == "__main__":
    # Use SelectorEventLoop on Windows for psycopg compatibility
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    print("Running Alembic migrations...")
    result = subprocess.run(
        ["python", "-m", "alembic", "upgrade", "head"], capture_output=True, text=True
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode == 0:
        print("Migrations completed successfully!")
    else:
        print(f"Migrations failed with exit code {result.returncode}")
        sys.exit(result.returncode)
