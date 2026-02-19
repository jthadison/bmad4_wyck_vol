-- PostgreSQL + TimescaleDB initialization script for BMAD Wyckoff system
-- This script runs automatically when the database is first created

-- Enable TimescaleDB extension (AC: TimescaleDB 2.13+)
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Enable UUID generation extension for primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Configure PostgreSQL settings for time-series workload
-- These settings optimize for OLAP-style queries on time-series data
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '8MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';

-- Note: Settings above require PostgreSQL restart to take effect
-- Docker will apply them on container startup

-- Grant necessary permissions on the current database to the current user
-- Uses dynamic SQL so it works regardless of POSTGRES_DB/POSTGRES_USER values
DO $$
BEGIN
  EXECUTE format('GRANT ALL PRIVILEGES ON DATABASE %I TO %I', current_database(), current_user);
END
$$;

-- Log initialization
SELECT 'Database initialized with TimescaleDB extension' AS status;
SELECT extversion AS timescaledb_version FROM pg_extension WHERE extname = 'timescaledb';
