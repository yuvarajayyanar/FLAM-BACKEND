import time
import subprocess
import signal
from . import db

SHUTDOWN_REQUESTED = False

def handle_sigterm(sig, frame):
    global SHUTDOWN_REQUESTED
    print("... Shutdown requested. Finishing current job, then exiting.")
    SHUTDOWN_REQUESTED = True

def run_worker_loop():
    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)
    print("Worker started. Waiting for jobs... (Press Ctrl+C to stop)")

    while not SHUTDOWN_REQUESTED:
        job = None
        try:
            job = db.fetch_and_lock_job()
            if job:
                print(f"Processing job {job['id']}...")
                
                job_timeout = job.get('timeout')
                
                try:
                    result = subprocess.run(
                        job['command'], 
                        shell=True, 
                        capture_output=True, 
                        text=True,
                        timeout=job_timeout
                    )
                    
                    if result.returncode == 0:
                        print(f"Completed job {job['id']}.")
                        db.update_job_status(job['id'], 'completed', result.stdout)
                    else:
                        print(f"Failed job {job['id']}. Error: {result.stderr}")
                        db.update_job_for_retry_or_dlq(
                            job['id'], job['command'], job['attempts'], result.stderr
                        )
                
                except subprocess.TimeoutExpired as e:
                    print(f"Job {job['id']} TIMED OUT after {job_timeout}s.")
                    error_log = f"Job failed: TimeoutExpired after {job_timeout}s"
                    db.update_job_for_retry_or_dlq(
                        job['id'], job['command'], job['attempts'], error_log
                    )
            
            else:
                time.sleep(1)
        
        except Exception as e:
            print(f"An error occurred: {e}")
            if job:
                db.update_job_for_retry_or_dlq(
                    job['id'], job['command'], job['attempts'], str(e)
                )
            time.sleep(5)
            
    print("Worker shutting down.")