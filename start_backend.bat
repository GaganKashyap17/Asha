@echo off
echo ============================================================
echo   ASHA Voice - Backend Server
echo   Django 4.2  |  Port 8000  |  MongoDB Atlas
echo ============================================================
cd /d "%~dp0backend"
if not exist venv\Scripts\python.exe (
    echo ERROR: Virtual environment not found.
    echo Run: python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
echo Starting Django server on http://localhost:8000 ...
venv\Scripts\python.exe manage.py runserver 8000
pause

venv\Scripts\activate
python manage.py runserver 8000