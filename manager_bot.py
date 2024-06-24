import subprocess
import time
import os
import signal
import atexit

# Path to your trading bot script
BOT_SCRIPT = "funding_bot.py"
LOG_FILE = "funding_bot.log"
LOCK_FILE = "./funding_bot.lock"

def create_lock_file():
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    print(f"Lock file created with PID {os.getpid()}")

def remove_lock_file():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
        print("Lock file removed")

def is_another_instance_running():
    try:
        result = subprocess.run(['pgrep', '-f', f'python3 {BOT_SCRIPT}'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        pids = result.stdout.split()
        print(f"Found PIDs: {pids}")
        current_pid = str(os.getpid())
        pids = [pid for pid in pids if pid != current_pid]
        print(f"Filtered PIDs: {pids}")
        if pids:
            return True
    except Exception as e:
        print(f"Error checking for running instances: {e}")
    return False

def start_bot():
    process = subprocess.Popen(['nohup', 'python3', BOT_SCRIPT, '&'], stdout=open(LOG_FILE, 'a'), stderr=subprocess.STDOUT, preexec_fn=os.setpgrp)
    return process

def stop_bot(process):
    os.killpg(os.getpgid(process.pid), signal.SIGTERM)

def manage_bot():
    if is_another_instance_running():
        print("Another instance is already running. Exiting.")
        return

    create_lock_file()
    atexit.register(remove_lock_file)

    while True:
        process = start_bot()
        print(f"Started bot with PID {process.pid}")
        time.sleep(15 * 60)  # Run for 15 minutes
        print(f"Stopping bot with PID {process.pid}")
        stop_bot(process)

if __name__ == "__main__":
    manage_bot()
