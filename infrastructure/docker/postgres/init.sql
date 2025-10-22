-- PostgreSQL initialization script for BMAD Wyckoff system
-- This script runs automatically when the database is first created

-- Create extensions (TimescaleDB will be added in later stories when needed)
-- For now, just ensure database is properly initialized

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE wyckoff_db TO wyckoff_user;

-- Log initialization
SELECT 'Database initialized successfully' AS status;
