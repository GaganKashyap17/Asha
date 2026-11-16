@echo off
echo ============================================================
echo   ASHA Voice - Frontend Dev Server
echo   React 18 + Vite  |  Port 5173
echo ============================================================
cd /d "%~dp0frontend"
if not exist node_modules (
    echo node_modules not found. Installing...
    npm install
)
echo Starting frontend on http://localhost:5173 ...
npm run dev
pause
