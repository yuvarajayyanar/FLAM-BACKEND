# QueueCTL - Background Job Queue System

QueueCTL is a command-line interface (CLI) application for managing a persistent, multi-worker background job queue. It is built in Python and uses a PostgreSQL database for job storage and for handling advanced concurrency control.

This system is designed to be robust, allowing multiple worker processes to safely consume jobs in parallel without duplication. It features an automatic retry mechanism with exponential backoff for failed jobs and a Dead Letter Queue (DLQ) for jobs that have permanently failed.

## Features

- **Persistent Job Storage:** Uses PostgreSQL to ensure jobs are not lost on application restart.
- **Safe Concurrency:** Supports multiple workers processing jobs in parallel using PostgreSQL's `SELECT ... FOR UPDATE SKIP LOCKED` to prevent race conditions and duplicate job execution.
- **Automatic Retries:** Failed jobs are automatically retried with an exponential backoff delay.
- **Dead Letter Queue (DLQ):** Jobs that fail a configurable number of times are moved to a DLQ for manual inspection and retry.
- **Configurable Settings:** CLI-based configuration for `max_retries` and `backoff_base`.
- **Job Lifecycle Management:** Full visibility into the job lifecycle (`pending`, `processing`, `completed`, `failed`, `dead`).
- **Bonus: Scheduled Jobs:** Jobs can be enqueued with a future `run_at` timestamp.
- **Bonus: Job Timeouts:** Individual jobs can be submitted with a `timeout` value, after which the worker will kill the job.
- **Bonus: Job Logging:** `stdout` and `stderr` from job execution are logged to the database for debugging.

## Demo Video

A full video demonstration of the application, including basic functionality, retries, DLQ management, and bonus features, can be found here:

[**QueueCTL Demo Video (Google Drive)**](https://drive.google.com/drive/folders/1j2bVZ1wFhJPfJrD8vMQBK8NErxYPYhi-?usp=drive_link)

## Local Setup & Installation

Follow these steps to set up and run the project on your local machine.

### 1. Prerequisites

- Python 3.10 or higher
- A running PostgreSQL server (version 12 or higher recommended)
- `git` (for cloning the repository)

### 2. Database Setup

You must first create a database and a dedicated user for the `queuectl` application.

1. Open `psql` or your preferred Postgres client as a superuser (e.g., `postgres`).
2. Run the following SQL commands:

```sql
CREATE DATABASE queue_db;
CREATE USER queue_user WITH PASSWORD 'queue_pass';
GRANT ALL PRIVILEGES ON DATABASE queue_db TO queue_user;
\c queue_db
GRANT ALL ON SCHEMA public TO queue_user;
