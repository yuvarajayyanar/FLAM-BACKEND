import os
import psycopg2
import datetime
from psycopg2.extras import RealDictCursor

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST'),
            dbname=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASS')
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error connecting to database: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if conn is None:
        print("Could not connect to DB, table not initialized.")
        return
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'job_state') THEN
                    CREATE TYPE job_state AS ENUM (
                        'pending', 'processing', 'completed', 'failed', 'dead'
                    );
                END IF;
            END $$;
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                state job_state DEFAULT 'pending',
                attempts INTEGER DEFAULT 0,
                output_log TEXT,
                dlq_summary TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                run_at TIMESTAMPTZ
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_pending_run_at
            ON jobs (state, run_at) WHERE state = 'pending';
        """)
        cur.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT);")
        cur.execute("""
            INSERT INTO config (key, value) VALUES ('max_retries', '3'), ('backoff_base', '2')
            ON CONFLICT (key) DO NOTHING;
        """)
    conn.commit()
    conn.close()
    print("Database and tables initialized successfully.")

def add_timeout_column():
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            try:
                cur.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS timeout INTEGER;")
                print("'timeout' column added to jobs table (if not exists).")
            except Exception as e:
                print(f"Error adding 'timeout' column: {e}")

def enqueue_job(job_id, command, run_at=None, timeout=None):
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (id, command, state, run_at, timeout) 
                VALUES (%s, %s, 'pending', %s, %s)
                """,
                (job_id, command, run_at, timeout)
            )

def list_jobs(state):
    conn = get_db_connection()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, command, state, attempts, created_at FROM jobs WHERE state = %s",
                (state,)
            )
            return cur.fetchall()

def fetch_and_lock_job():
    conn = get_db_connection()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE jobs
                SET state = 'processing', run_at = %s
                WHERE id = (
                    SELECT id FROM jobs
                    WHERE state = 'pending' AND (run_at IS NULL OR run_at <= NOW())
                    ORDER BY created_at
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, command, attempts, timeout;
                """,
                (datetime.datetime.now(),)
            )
            return cur.fetchone()

def update_job_status(job_id, state, log_output=None):
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET state = %s, output_log = %s WHERE id = %s",
                (state, log_output, job_id)
            )

def get_config_value(key):
    conn = get_db_connection()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT value FROM config WHERE key = %s", (key,))
            row = cur.fetchone()
            return row['value'] if row else None

def update_job_for_retry_or_dlq(job_id, command, current_attempts, log_output):
    conn = get_db_connection()
    with conn:
        try:
            max_retries = int(get_config_value('max_retries'))
            backoff_base = int(get_config_value('backoff_base'))
            
            new_attempts = current_attempts + 1
            
            if new_attempts >= max_retries:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE jobs SET state = 'dead', attempts = %s, output_log = %s WHERE id = %s",
                        (new_attempts, log_output, job_id)
                    )
                print(f"Job {job_id} failed permanently. Moved to DLQ.")
            else:
                delay_seconds = backoff_base ** new_attempts
                new_run_at = datetime.datetime.now() + datetime.timedelta(seconds=delay_seconds)
                
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE jobs SET state = 'pending', attempts = %s, run_at = %s, output_log = %s WHERE id = %s",
                        (new_attempts, new_run_at, log_output, job_id)
                    )
                print(f"Job {job_id} failed. Retrying in {delay_seconds}s (Attempt {new_attempts}).")
                
        except Exception as e:
            print(f"Error handling failed job {job_id}: {e}")

def set_config_value(key, value):
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO config (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
                """,
                (key, value)
            )

def retry_dlq_job(job_id):
    conn = get_db_connection()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE jobs
                SET state = 'pending', attempts = 0, run_at = NULL, output_log = NULL
                WHERE id = %s AND state = 'dead'
                RETURNING id;
                """,
                (job_id,)
            )
            return cur.fetchone()

def get_job_status_summary():
    conn = get_db_connection()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT state, COUNT(*) as count FROM jobs GROUP BY state")
            return cur.fetchall()