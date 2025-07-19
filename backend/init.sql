-- AI Social Media Creator Database Initialization Script
-- This script sets up the database and user for the application

-- Create database (if not exists)
CREATE DATABASE IF NOT EXISTS socialmedia_creator;

-- Create user for the application
CREATE USER IF NOT EXISTS smcreator WITH PASSWORD 'change_this_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE socialmedia_creator TO smcreator;
GRANT CONNECT ON DATABASE socialmedia_creator TO smcreator;

-- Switch to the application database
\c socialmedia_creator;

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO smcreator;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO smcreator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO smcreator;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO smcreator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO smcreator;

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Initial data or configuration can be added here
-- For example, default platform configurations, etc.

-- Log the initialization
INSERT INTO public.system_log (message, created_at) 
VALUES ('Database initialized successfully', NOW())
ON CONFLICT DO NOTHING;

