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


# --- QueueCTL Full System Test ---

Write-Host "---"
Write-Host " STEP 1: Setting config 'max_retries' to 2 for a faster test."
# We set max_retries to 2 (initial attempt + 1 retry)
queuectl config set max_retries 2
Write-Host "---"

# ---
# STEP 2: Enqueue all jobs
# ---

Write-Host " STEP 2: Enqueuing all 4 job types..."

# Job 1: Success
$success_job = @'
{"id":"success-1", "command":"echo 'This job will pass'"}
'@
$success_job | queuectl enqueue

# Job 2: Fail (to test DLQ)
$fail_job = @'
{"id":"fail-1", "command":"dir X:\nonexistent-path"}
'@
$fail_job | queuectl enqueue

# Job 3: Timeout (Bonus)
$timeout_job = @'
{"id":"timeout-1", "command":"sleep 10", "timeout": 2}
'@
$timeout_job | queuectl enqueue

# Job 4: Scheduled (Bonus)
# We set this to run 15 seconds in the future
# Job 4: Scheduled (Bonus)
$run_at_time = (Get-Date).AddSeconds(15).ToString("o")
$scheduled_job = @"
{"id":"scheduled-1", "command":"echo 'The scheduled job ran!'", "run_at": "$run_at_time"}
"@
Write-Host "   ...Submitting scheduled job for $run_at_time"
$scheduled_job | queuectl enqueue

Write-Host "---"

# ---
# STEP 3: Wait for processing
# ---

Write-Host " STEP 3: Waiting 20 seconds for all jobs to be processed..."
Write-Host "(Watch the worker terminal!)"
# This wait gives time for:
# 1. Success job to run (1s)
# 2. Fail job to try, retry (2s), and go to DLQ (total ~3s)
# 3. Timeout job to try, retry (2s), and go to DLQ (total ~3s)
# 4. Scheduled job's timer to be hit (15s) and run (1s)
Start-Sleep 20

# ---
# STEP 4: First Report
# ---

Write-Host "---"
Write-Host " STEP 4: Initial Report - Checking job status..."
queuectl status
Write-Host "---"
Write-Host "Checking DLQ for failed and timed-out jobs..."
queuectl dlq list
Write-Host "---"

# ---
# STEP 5: Test DLQ Retry
# ---

Write-Host " STEP 5: Testing DLQ... Retrying the 'fail-1' job."
queuectl dlq retry fail-1
Write-Host "---"
Write-Host "Waiting 5 seconds for the retried job to fail again..."
# This wait gives time for:
# 1. 'fail-1' to run (1s), fail, retry (2s), and go back to DLQ
Start-Sleep 5

# ---
# STEP 6: Final Report
# ---

Write-Host "---"
Write-Host "STEP 6: Final Report - 'fail-1' should be back in the DLQ."
queuectl status
Write-Host "---"
Write-Host "Final DLQ state:"
queuectl dlq list
Write-Host "---"
Write-Host " Demo complete."  