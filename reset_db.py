import sqlite3

# Delete the old database and start fresh
import os
if os.path.exists("scheduler.db"):
    os.remove("scheduler.db")

# Connect to new database
conn = sqlite3.connect("scheduler.db")
cursor = conn.cursor()

# Create new tables with correct schema
cursor.executescript("""
-- Create table for student records
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matric TEXT NOT NULL UNIQUE,
    department TEXT NOT NULL,
    level TEXT,
    slot INTEGER,
    course_code TEXT
);

-- Create table for time range for each slot
CREATE TABLE IF NOT EXISTS slot_times (
    slot INTEGER PRIMARY KEY,
    start_time TEXT,
    end_time TEXT
);

-- Create table for reschedule requests
CREATE TABLE IF NOT EXISTS reschedule_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matric TEXT NOT NULL,
    requested_slot INTEGER NOT NULL,
    reason TEXT,
    status TEXT DEFAULT 'Pending'
);
""")

conn.commit()
conn.close()

print("Database reset and all tables created successfully.")
