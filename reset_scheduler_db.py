import sqlite3

# Connect to database
conn = sqlite3.connect("scheduler.db")
cursor = conn.cursor()

# Drop existing tables to ensure clean structure
cursor.executescript("""
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS slot_times;
DROP TABLE IF EXISTS reschedule_requests;

-- Create table for student records
CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matric TEXT NOT NULL UNIQUE,
    department TEXT NOT NULL,
    level TEXT,
    slot INTEGER,
    course_code TEXT
);

-- Create table for time range for each slot
CREATE TABLE slot_times (
    slot INTEGER PRIMARY KEY,
    start_time TEXT,
    end_time TEXT
);

-- Create table for reschedule requests
CREATE TABLE reschedule_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matric TEXT NOT NULL,
    requested_slot INTEGER NOT NULL,
    reason TEXT,
    status TEXT DEFAULT 'Pending'
);
""")

conn.commit()
print("All tables dropped and recreated successfully.")
