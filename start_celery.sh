#!/bin/bash
echo "Starting Celery Worker and Beat for WizzyDjango..."
echo ""

# Check if Redis is running
echo "Checking if Redis is running..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "ERROR: Redis server is not running!"
    echo "Please start Redis server first, then try again."
    echo "You can install Redis with: sudo apt-get install redis-server"
    echo ""
    exit 1
else
    echo "Redis is running - OK"
fi

echo ""

# Set up environment
export DJANGO_SETTINGS_MODULE=wizzydjango.settings.development
echo "Using settings module: $DJANGO_SETTINGS_MODULE"
echo ""

# Check for existing Celery workers and beat
echo "Checking for existing Celery processes..."
if pgrep -f "celery worker\|celery beat" > /dev/null; then
    echo "Found existing Celery processes. Stopping them..."
    pkill -f "celery worker\|celery beat"
    sleep 2
else
    echo "No existing Celery processes found."
fi

# Create logs directory if it doesn't exist
if [ ! -d "logs" ]; then
    echo "Creating logs directory..."
    mkdir -p logs
fi

echo "Starting Celery worker..."
celery -A wizzydjango worker -l info --logfile=logs/celery_worker.log --detach

echo "Starting Celery beat scheduler..."
celery -A wizzydjango beat -l info --logfile=logs/celery_beat.log --detach

echo ""
echo "Celery worker and beat scheduler are running in the background."
echo "Check logs/celery_worker.log and logs/celery_beat.log for details."
echo "Use 'pkill -f \"celery worker\|celery beat\"' to stop Celery processes."
echo "" 