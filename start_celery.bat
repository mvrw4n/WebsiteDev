@echo off
echo Starting Celery Worker and Beat for WizzyDjango...
echo.

REM Check if Redis is running first by attempting to connect to it
echo Checking if Redis is running...
redis-cli ping > nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Redis server is not running!
    echo Please start Redis server first, then try again.
    echo You can download Redis for Windows from: https://github.com/microsoftarchive/redis/releases
    echo.
    goto :end
) else (
    echo Redis is running - OK
)

echo.

cd /d "%~dp0"
set DJANGO_SETTINGS_MODULE=wizzydjango.settings.development

echo Using settings module: %DJANGO_SETTINGS_MODULE%
echo.

REM Check for any existing Celery workers and beat
echo Checking for existing Celery processes...
tasklist /FI "IMAGENAME eq celery.exe" 2>NUL | find /I /N "celery.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo Found existing Celery processes. Stopping them...
    taskkill /F /IM celery.exe
    timeout /t 2 /nobreak > nul
) else (
    echo No existing Celery processes found.
)

REM Create logs directory if it doesn't exist
if not exist "logs\" (
    echo Creating logs directory...
    mkdir logs
)

echo Starting Celery worker in background...
start /B "" celery -A wizzydjango worker -l info --logfile=logs/celery_worker.log --pool=solo -E

echo Starting Celery beat scheduler in background...
start /B "" celery -A wizzydjango beat -l info --logfile=logs/celery_beat.log

echo.
echo Celery worker and beat scheduler are running in the background.
echo Check logs/celery_worker.log and logs/celery_beat.log for details.
echo To stop Celery processes, use Task Manager or run 'taskkill /F /IM celery.exe'

:end
echo.
echo Press any key to exit...
pause > nul 