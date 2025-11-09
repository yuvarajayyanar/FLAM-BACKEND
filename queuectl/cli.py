import click
import json
from . import db
from . import worker as worker_module

@click.group()
def cli():
    """
    queuectl: A CLI for managing the background job queue.
    """
    pass

@cli.command()
def initdb():
    """
    Initializes the database and creates tables.
    """
    click.echo("Initializing database...")
    db.init_db()

@cli.command()
def upgrade_db():
    """
    (One-time) Adds new columns for bonus features.
    """
    click.echo("Applying database upgrades...")
    db.add_timeout_column()
    click.echo("Database upgrade complete.")

@cli.command()
@click.argument('job_data_json', required=False)
def enqueue(job_data_json):
    """
    Enqueues a new job.
    
    Reads job data from an argument or stdin.
    JSON format: '{"id":"job1", "command":"sleep 2", "run_at": "2025-11-10T10:00:00Z", "timeout": 30}'
    """
    if not job_data_json:
        try:
            job_data_json = click.get_text_stream('stdin').read()
        except Exception as e:
            click.echo(f"Error reading from stdin: {e}")
            return

    try:
        job_data = json.loads(job_data_json)
        job_id = job_data.get('id')
        command = job_data.get('command')
        
        run_at = job_data.get('run_at') 
        timeout = job_data.get('timeout')

        if not job_id or not command:
            click.echo("Error: JSON data must include 'id' and 'command'.")
            return

        click.echo(f"Enqueuing job {job_id}...")
        db.enqueue_job(job_id, command, run_at, timeout)
        
        if run_at:
            click.echo(f"Job {job_id} scheduled to run at {run_at}.")
        else:
            click.echo(f"Job {job_id} enqueued successfully.")
    
    except json.JSONDecodeError:
        click.echo("Error: Invalid JSON string provided.")
    except Exception as e:
        click.echo(f"An error occurred: {e}")

@cli.command()
@click.option('--state', default='pending', help="The state to list jobs for (pending, completed, etc.)")
def list(state):
    """
    List jobs in the queue by state.
    """
    try:
        jobs = db.list_jobs(state)
        if not jobs:
            click.echo(f"No jobs found with state: {state}")
            return
        
        click.echo(f"--- Jobs ({state}) ---")
        for job in jobs:
            click.echo(f"  ID       : {job['id']}")
            click.echo(f"  Command  : {job['command']}")
            click.echo(f"  Attempts : {job['attempts']}")
            click.echo(f"  Created  : {job['created_at']}")
            click.echo("-" * 20)
            
    except Exception as e:
        click.echo(f"An error occurred: {e}")

@cli.command()
def status():
    """
    Show a summary of all job states.
    """
    try:
        summary = db.get_job_status_summary()
        if not summary:
            click.echo("No jobs found.")
            return
        
        click.echo("--- Job Status Summary ---")
        for row in summary:
            click.echo(f"  {row['state']:<12}: {row['count']}")
    
    except Exception as e:
        click.echo(f"An error occurred: {e}")

# --- Worker Commands ---

@cli.group()
def worker():
    """
    Manage worker processes.
    """
    pass

@worker.command()
def start():
    """
    Start a new worker process.
    """
    worker_module.run_worker_loop()

# --- Config Commands ---

@cli.group()
def config():
    """
    Manage configuration settings.
    """
    pass

@config.command()
@click.argument('key')
@click.argument('value')
def set(key, value):
    """
    Set a configuration value (e.g., config set max_retries 3).
    """
    try:
        db.set_config_value(key, value)
        click.echo(f"Config set: {key} = {value}")
    except Exception as e:
        click.echo(f"Error setting config: {e}")

# --- DLQ Commands ---

@cli.group()
def dlq():
    """
    Manage the Dead Letter Queue.
    """
    pass

@dlq.command(name='list')
def list_dlq():
    """
    List all jobs in the DLQ.
    """
    try:
        jobs = db.list_jobs('dead')
        if not jobs:
            click.echo("No jobs found in DLQ.")
            return
        
        click.echo("--- Dead Letter Queue Jobs ---")
        for job in jobs:
            click.echo(f"  ID       : {job['id']}")
            click.echo(f"  Command  : {job['command']}")
            click.echo(f"  Attempts : {job['attempts']}")
            click.echo(f"  Created  : {job['created_at']}")
            click.echo("-" * 20)
            
    except Exception as e:
        click.echo(f"An error occurred: {e}")

@dlq.command()
@click.argument('job_id')
def retry(job_id):
    """
    Retry a specific job from the DLQ by its ID.
    """
    try:
        result = db.retry_dlq_job(job_id)
        if result:
            click.echo(f"Job {job_id} sent back to 'pending' queue.")
        else:
            click.echo(f"Job {job_id} not found in DLQ.")
    except Exception as e:
        click.echo(f"Error retrying job: {e}")

if __name__ == '__main__':
    cli()