# QueueCTL - Background Job Queue System

QueueCTL is a command-line interface (CLI) application for managing a persistent, multi-worker background job queue. It is built in Python and uses a PostgreSQL database for job storage and for handling advanced concurrency control.

This system is designed to be robust, allowing multiple worker processes to safely consume jobs in parallel without duplication. It features an automatic retry mechanism with exponential backoff for failed jobs and a Dead Letter Queue (DLQ) for jobs that have permanently failed.

##  Demo Video

You can view a full demo of **QueueCTL** in action here:  
[**Watch Demo Video on Google Drive**](https://drive.google.com/drive/folders/1j2bVZ1wFhJPfJrD8vMQBK8NErxYPYhi-?usp=drive_link)

---

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
```

### 3. Project & Environment Setup

1. Clone the repository:
   ```bash
   git clone <your-github-repo-link>
   cd queuectl
   ```

2. Create and activate a Python virtual environment:
   ```powershell
   # Windows
   python -m venv venv
   .\venv\Scripts\Activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install the `queuectl` CLI in "editable" mode:
   ```bash
   pip install -e .
   ```

### 4. Environment Variables

Set the environment variables for PostgreSQL connection and Python output buffering:

```powershell
# PowerShell
$env:DB_HOST = "localhost"
$env:DB_NAME = "queue_db"
$env:DB_USER = "queue_user"
$env:DB_PASS = "queue_pass"

# For unbuffered, real-time output from workers
$env:PYTHONUNBUFFERED = "1"
```

### 5. Initialize the Database

Run the following commands to initialize and upgrade the database schema.

```powershell
queuectl initdb
queuectl upgrade-db
```

## Usage Examples

All commands must be executed from an activated `venv` with environment variables set.

### Starting a Worker

Start a background worker to process jobs:

```powershell
queuectl worker start
```

### Running Multiple Workers

Open multiple terminals, activate the virtual environment in each, and start additional workers for concurrent processing.

### Enqueuing a Job

Jobs are submitted as JSON through standard input:

```powershell
$json = @'
{"id":"job-001", "command":"echo 'Hello World'"}
'@
$json | queuectl enqueue
```

### Enqueuing a Scheduled Job with Timeout

You can include `run_at` (ISO 8601 format) and `timeout` (in seconds):

```powershell
$json = @'
{
  "id": "job-002",
  "command": "sleep 10",
  "run_at": "2025-11-10T10:00:00+05:30",
  "timeout": 2
}
'@
$json | queuectl enqueue
```

### Checking System Status

View the overall job summary:

```powershell
queuectl status
```

**Example Output:**
```
--- Job Status Summary ---
  completed   : 10
  dead        : 2
  pending     : 5
```

### Listing Jobs

List jobs filtered by state:

```powershell
queuectl list --state pending
queuectl list --state completed
```

### Managing the Dead Letter Queue (DLQ)

1. **List failed jobs:**
   ```powershell
   queuectl dlq list
   ```

2. **Retry a failed job:**
   ```powershell
   queuectl dlq retry job-002
   ```

### Managing Configuration

Change system configuration options such as maximum retries:

```powershell
queuectl config set max_retries 2
```

## Architecture & Design Decisions

### 1. Persistence & Concurrency (PostgreSQL)

**PostgreSQL** provides robust transaction control, which is used to prevent duplicate job consumption.

The following query in `db.py` ensures atomic job selection and locking:

```sql
UPDATE jobs
SET state = 'processing', ...
WHERE id = (
    SELECT id FROM jobs
    WHERE state = 'pending' AND (run_at IS NULL OR run_at <= NOW())
    ORDER BY created_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
RETURNING ...;
```

`FOR UPDATE SKIP LOCKED` ensures that when multiple workers request jobs simultaneously, each gets a unique job without collisions.

### 2. CLI Framework

Built using the **`click`** library, providing structured subcommands (e.g., `worker`, `config`, `dlq`) and automatic help generation.

### 3. Assumptions & Trade-offs

- **Worker Count:** Rather than handling multiple processes internally, this version recommends running multiple terminals to simulate concurrency.
- **Worker Stop Command:** A `worker stop` command was not implemented. Workers can be safely terminated using `Ctrl+C`, which triggers a graceful shutdown.

## Testing Instructions

A PowerShell script `test_flows.ps1` can be used to verify core functionality.

**Terminal 1:** Start the worker  
```powershell
queuectl worker start
```

**Terminal 2:** Run the following script:

```powershell
# test_flows.ps1

Write-Host "--- 1. Setting config ---"
queuectl config set max_retries 2

Write-Host "--- 2. Enqueuing a job that will SUCCEED ---"
$success_job = @'
{"id":"success-1", "command":"echo 'This job will pass'"}
'@
$success_job | queuectl enqueue

Write-Host "--- 3. Enqueuing a job that will FAIL ---"
$fail_job = @'
{"id":"fail-1", "command":"dir X:\nonexistent-path"}
'@
$fail_job | queuectl enqueue

Write-Host "--- 4. Enqueuing a job that will TIME OUT ---"
$timeout_job = @'
{"id":"timeout-1", "command":"sleep 10", "timeout": 2}
'@
$timeout_job | queuectl enqueue

Write-Host "--- 5. Waiting 10 seconds for jobs to process... ---"
Start-Sleep 10

Write-Host "--- 6. Checking final status ---"
queuectl status

Write-Host "--- 7. Checking Dead Letter Queue ---"
queuectl dlq list

Write-Host "--- 8. Retrying the failed job ---"
queuectl dlq retry fail-1
```
