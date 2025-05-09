#!/usr/bin/env python
"""
Helper script to start Celery workers with proper settings
This avoids many environment and path issues that can occur
"""
import os
import sys
import django
from subprocess import Popen
import time
import argparse
import signal
import psutil

# Parse command line arguments
parser = argparse.ArgumentParser(description='Start Celery worker and beat for Wizzy')
parser.add_argument('--no-beat', action='store_true', help='Do not start the beat scheduler')
parser.add_argument('--concurrency', type=int, default=4, help='Number of worker processes (default: 4)')
parser.add_argument('--loglevel', default='info', help='Log level: debug, info, warning, error, critical')
parser.add_argument('--queue', default='celery', help='Queue to consume from')
args = parser.parse_args()

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wizzydjango.settings.base')

# Ensure Django is set up
django.setup()

# Command for Celery worker
worker_cmd = [
    "celery", 
    "-A", "wizzydjango", 
    "worker", 
    f"--loglevel={args.loglevel}",
    f"--concurrency={args.concurrency}",
    f"--queues={args.queue}",
    "--logfile=logs/celery_worker.log",
    "--without-heartbeat",  # Reduces overhead on systems with many workers
    "--without-mingle",     # Reduces startup overhead
    "--pool=prefork",       # Best for CPU-bound tasks
]

# Command for Celery beat
beat_cmd = [
    "celery", 
    "-A", "wizzydjango", 
    "beat", 
    f"--loglevel={args.loglevel}",
    "--logfile=logs/celery_beat.log",
    "--scheduler=django_celery_beat.schedulers:DatabaseScheduler" # Use Django database scheduler
]

# Track all processes we create
all_processes = []

def terminate_all_processes():
    """Terminate all processes and their children"""
    print("\nShutting down all Celery processes...")
    
    for proc in all_processes:
        if proc.poll() is None:  # Process is still running
            # Get the main process
            try:
                parent = psutil.Process(proc.pid)
                
                # Get all children
                children = parent.children(recursive=True)
                
                # Terminate children first
                for child in children:
                    print(f"Terminating child process {child.pid}...")
                    try:
                        child.terminate()
                    except:
                        pass
                
                # Terminate the main process
                print(f"Terminating process {proc.pid}...")
                proc.terminate()
                
                # Wait for termination
                try:
                    proc.wait(timeout=3)
                except:
                    # Force kill if it didn't terminate
                    print(f"Force killing process {proc.pid}...")
                    try:
                        parent.kill()
                    except:
                        pass
                    
            except psutil.NoSuchProcess:
                # Process already gone
                pass
    
    print("All Celery processes terminated.")

def signal_handler(sig, frame):
    """Handle termination signals"""
    print("\nReceived termination signal. Shutting down...")
    terminate_all_processes()
    sys.exit(0)

def start_worker():
    """Start the Celery worker"""
    print(f"Starting Celery worker with {args.concurrency} processes, log level: {args.loglevel}...")
    worker_process = Popen(worker_cmd)
    all_processes.append(worker_process)
    return worker_process

def start_beat():
    """Start the Celery beat scheduler"""
    print(f"Starting Celery beat scheduler with log level: {args.loglevel}...")
    beat_process = Popen(beat_cmd)
    all_processes.append(beat_process)
    return beat_process

if __name__ == "__main__":
    # Set up signal handlers for proper termination
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Django settings module:", os.environ.get('DJANGO_SETTINGS_MODULE'))
    print("Secret key available:", bool(django.conf.settings.SECRET_KEY))
    
    # Start worker process
    worker_process = start_worker()
    
    # Start beat process by default unless --no-beat is specified
    beat_process = None
    if not args.no_beat:
        time.sleep(2)  # Wait a bit for worker to start
        beat_process = start_beat()
    
    try:
        # Keep script running
        print("\nCelery processes are running. Press Ctrl+C to stop...")
        print(f"Check logs/celery_worker.log and logs/celery_beat.log for details.")
        
        # Wait for worker process to exit
        while True:
            # Check if processes are still running
            if worker_process.poll() is not None:
                print("Worker process exited unexpectedly.")
                break
                
            if beat_process and beat_process.poll() is not None:
                print("Beat process exited unexpectedly.")
                break
                
            time.sleep(1)
            
    except KeyboardInterrupt:
        # This is handled by the signal_handler
        pass
    finally:
        # Always make sure to terminate processes
        terminate_all_processes()
        sys.exit(0) 