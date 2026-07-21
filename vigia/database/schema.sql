-- Vigia SQLite Schema
-- Uses surrogate keys (id) to allow raw ingestion of corrupted records for auditing

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT,
    name TEXT,
    status TEXT,
    budget REAL,
    deadline TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    project_id TEXT,
    assignee TEXT,
    status TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS communications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT,
    project_id TEXT,
    channel TEXT,
    summary TEXT,
    sentiment REAL,
    timestamp TEXT
);
