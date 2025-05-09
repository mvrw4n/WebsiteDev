#!/usr/bin/env python
"""
Celery Debug Tool for WizzyDjango
----------------------------------
This script helps diagnose Celery connection issues by:
1. Checking Django settings for Celery
2. Testing Redis connection
3. Checking for running Celery workers
4. Showing process info for Celery workers
5. Testing a simple Celery task
"""

import os
import sys
import time
import socket
import subprocess
from datetime import datetime
import json
import redis

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wizzydjango.settings.development')

print("=" * 60)
print("CELERY DIAGNOSTIC TOOL")
print("=" * 60)
print()

# Step 1: Initialize Django
print("STEP 1: Initializing Django...")
try:
    import django
    django.setup()
    print("Django initialized successfully.")
    print(f"Django version: {django.get_version()}")
    print(f"Django settings module: {os.environ.get('DJANGO_SETTINGS_MODULE')}")
    
    from django.conf import settings
    print(f"Project BASE_DIR: {settings.BASE_DIR}")
except Exception as e:
    print(f"ERROR initializing Django: {str(e)}")
    sys.exit(1)

print("\n" + "=" * 60 + "\n")

# Step 2: Import Celery app and check settings
print("STEP 2: Checking Celery configuration...")
try:
    from wizzydjango.celery import app
    
    # Print Celery settings
    broker_url = app.conf.get('broker_url', 'Not set')
    result_backend = app.conf.get('result_backend', 'Not set')
    
    print(f"Celery broker URL: {broker_url}")
    print(f"Celery result backend: {result_backend}")
    
    # Check if broker URL looks valid
    if not broker_url or broker_url == 'Not set':
        print("ERROR: Broker URL is not set!")
    elif 'redis://' not in broker_url and 'amqp://' not in broker_url:
        print(f"WARNING: Broker URL doesn't look like Redis or RabbitMQ: {broker_url}")
    
    # Check if result backend looks valid
    if not result_backend or result_backend == 'Not set':
        print("WARNING: Result backend is not set. Task results may not be stored.")
    
except Exception as e:
    print(f"ERROR importing Celery app: {str(e)}")
    sys.exit(1)

print("\n" + "=" * 60 + "\n")

# Step 3: Check Redis connection
print("STEP 3: Checking Redis connection...")
try:
    # Parse Redis URL from broker URL
    if 'redis://' in broker_url:
        # Simple parsing for redis://host:port/db format
        from urllib.parse import urlparse
        parsed = urlparse(broker_url)
        redis_host = parsed.hostname or 'localhost'
        redis_port = parsed.port or 6379
        redis_db = int(parsed.path.strip('/') or 0)
        redis_password = parsed.password
        
        print(f"Redis connection details:")
        print(f"  Host: {redis_host}")
        print(f"  Port: {redis_port}")
        print(f"  DB: {redis_db}")
        print(f"  Password: {'Set' if redis_password else 'Not set'}")
        
        # Try to connect to Redis
        r = redis.Redis(
            host=redis_host, 
            port=redis_port,
            db=redis_db,
            password=redis_password,
            socket_timeout=5
        )
        
        # Ping Redis
        print("Trying to ping Redis...")
        redis_ping = r.ping()
        if redis_ping:
            print("✓ Redis responded to PING - connection successful!")
            
            # Get Redis info
            redis_info = r.info()
            print(f"Redis version: {redis_info.get('redis_version')}")
            print(f"Connected clients: {redis_info.get('connected_clients')}")
            print(f"Used memory: {redis_info.get('used_memory_human')}")
        else:
            print("✗ Redis did not respond to PING.")
    else:
        print("Not using Redis as broker - skipping Redis check.")
except Exception as e:
    print(f"ERROR connecting to Redis: {str(e)}")

print("\n" + "=" * 60 + "\n")

# Step 4: Check for Celery workers
print("STEP 4: Checking for Celery workers...")

# Try to ping workers
print("Pinging Celery workers...")
try:
    ping_result = app.control.ping(timeout=2.0)
    
    if ping_result:
        print(f"✓ Found {len(ping_result)} worker(s) running!")
        
        # Print worker details
        for i, worker_response in enumerate(ping_result, 1):
            if isinstance(worker_response, dict):
                for worker_name, response in worker_response.items():
                    print(f"  Worker #{i}: {worker_name}")
                    print(f"    Response: {response}")
            else:
                print(f"  Worker #{i}: {worker_response}")
                
        # Get more detailed worker info
        print("\nGetting worker stats...")
        insp = app.control.inspect()
        
        # Get active tasks
        active = insp.active() or {}
        print("\nActive tasks:")
        if not active:
            print("  No active tasks")
        else:
            for worker_name, tasks in active.items():
                print(f"  {worker_name}: {len(tasks)} active tasks")
                for task in tasks:
                    print(f"    - {task.get('name')} (id: {task.get('id')})")
        
        # Get scheduled tasks
        scheduled = insp.scheduled() or {}
        print("\nScheduled tasks:")
        if not scheduled:
            print("  No scheduled tasks")
        else:
            for worker_name, tasks in scheduled.items():
                print(f"  {worker_name}: {len(tasks)} scheduled tasks")
        
        # Get reserved tasks
        reserved = insp.reserved() or {}
        print("\nReserved tasks:")
        if not reserved:
            print("  No reserved tasks")
        else:
            for worker_name, tasks in reserved.items():
                print(f"  {worker_name}: {len(tasks)} reserved tasks")
        
        # Get registered tasks
        registered = insp.registered() or {}
        print("\nRegistered task types:")
        if not registered:
            print("  No registered tasks")
        else:
            for worker_name, tasks in registered.items():
                print(f"  {worker_name} can handle:")
                for task in sorted(tasks):
                    print(f"    - {task}")
    else:
        print("✗ No workers responded to ping!")
        
        # Check for Celery processes
        print("\nChecking operating system for Celery processes...")
        
        try:
            if os.name == 'nt':  # Windows
                # Use tasklist to find celery processes
                result = subprocess.run('tasklist /FI "IMAGENAME eq celery.exe"', 
                                        shell=True, 
                                        capture_output=True, 
                                        text=True)
                output = result.stdout
                
                if "celery.exe" in output:
                    print("Found celery.exe processes in Windows Task Manager:")
                    for line in output.splitlines():
                        if "celery.exe" in line:
                            print(f"  {line.strip()}")
                else:
                    print("No celery.exe processes found in Windows Task Manager.")
                    
                # Also check for python processes that might be Celery workers
                result = subprocess.run('tasklist /FI "IMAGENAME eq python.exe"', 
                                        shell=True, 
                                        capture_output=True, 
                                        text=True)
                output = result.stdout
                
                if "python.exe" in output:
                    print("\nFound python.exe processes that might be running Celery:")
                    for line in output.splitlines():
                        if "python.exe" in line:
                            print(f"  {line.strip()}")
            else:  # Unix-like
                # Use ps to find celery processes
                result = subprocess.run(['ps', 'aux', '|', 'grep', 'celery'], 
                                        shell=True, 
                                        capture_output=True, 
                                        text=True)
                output = result.stdout
                
                if output:
                    print("Found possible Celery processes:")
                    for line in output.splitlines():
                        if "grep" not in line:  # Exclude the grep process itself
                            print(f"  {line.strip()}")
                else:
                    print("No Celery processes found.")
        except Exception as e:
            print(f"Error checking for Celery processes: {str(e)}")
        
        # Check network ports
        print("\nChecking network ports...")
        try:
            # Check if Redis port is open
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(('localhost', 6379))
            if result == 0:
                print("✓ Redis port (6379) is open")
            else:
                print("✗ Redis port (6379) is not open")
            s.close()
            
            # Also check common Celery ports
            common_ports = [5672]  # RabbitMQ default
            open_ports = []
            
            for port in common_ports:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                result = s.connect_ex(('localhost', port))
                if result == 0:
                    open_ports.append(port)
                s.close()
                
            if open_ports:
                print(f"Open ports related to message brokers: {open_ports}")
            else:
                print("No common message broker ports found open.")
                
        except Exception as e:
            print(f"Error checking network ports: {str(e)}")
            
except Exception as e:
    print(f"ERROR checking for Celery workers: {str(e)}")

print("\n" + "=" * 60 + "\n")

# Step 5: Try running a test task
print("STEP 5: Testing a simple Celery task...")
try:
    from scraping.tasks import test_celery_connection
    
    print("Sending test task to Celery...")
    result = test_celery_connection.delay()
    task_id = result.id
    print(f"Task submitted with ID: {task_id}")
    
    # Wait for the task to complete
    print("Waiting for task result (timeout 5 seconds)...")
    try:
        task_result = result.get(timeout=5)
        print("\nTask completed successfully!")
        print("Task result:")
        print(json.dumps(task_result, indent=2))
    except Exception as e:
        print(f"\nError getting task result: {str(e)}")
        print("This could mean:")
        print("1. The task is still running (slow execution)")
        print("2. The worker crashed while processing the task")
        print("3. The result backend is not properly configured")
        print("4. There are no workers to process the task")
except Exception as e:
    print(f"ERROR running test task: {str(e)}")

print("\n" + "=" * 60 + "\n")

# Print final summary and recommendations
print("DIAGNOSTIC SUMMARY:")
print("------------------")
print("1. Make sure Redis is installed and running")
print("2. Ensure Celery worker is started with: celery -A wizzydjango worker -l info --pool=solo")
print("3. Check that your CELERY_BROKER_URL and CELERY_RESULT_BACKEND are correctly set")
print("4. If using Windows, use the --pool=solo flag with Celery")
print("\nFor more information, see: https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/")
print("\n" + "=" * 60) 