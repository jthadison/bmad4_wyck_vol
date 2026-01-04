from sqlalchemy import create_engine, text

engine = create_engine("postgresql+psycopg://bmad:bmad_dev_password@localhost:5432/bmad_wyckoff")
with engine.connect() as conn:
    result = conn.execute(
        text("DELETE FROM backtest_results WHERE created_at < NOW() - INTERVAL '1 hour'")
    )
    conn.commit()
    print(f"Deleted {result.rowcount} old records")
