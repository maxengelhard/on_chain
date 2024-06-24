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

def remove_lock_file():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

def is_another_instance_running():
    # Check for running instances of funding_bot.py
    result = subprocess.run(['pgrep', '-f', BOT_SCRIPT], stdout=subprocess.PIPE)
    pids = result.stdout.decode().split()
    current_pid = str(os.getpid())
    filtered_pids = [pid for pid in pids if pid != current_pid]
    return len(filtered_pids) > 0

def start_bot():
    # Start the bot with nohup and redirect output to a log file
    process = subprocess.Popen(['nohup', 'python3', BOT_SCRIPT], stdout=open(LOG_FILE, 'a'), stderr=subprocess.STDOUT, preexec_fn=os.setpgrp)
    return process

def stop_bot(process):
    # Kill the process group started by nohup
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
        time.sleep(14 * 60)  # Run for 14 minutes. Errors happen around 15
        print(f"Stopping bot with PID {process.pid}")
        stop_bot(process)

if __name__ == "__main__":
    manage_bot()
