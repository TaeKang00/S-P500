@echo off
cd /d "%~dp0"

echo [1/2] Starting backend...
start "S&P500 Backend" cmd /k "cd backend && (if not exist .venv python -m venv .venv) && .venv\Scripts\activate && pip install -r requirements.txt -q && python run.py"

echo [2/2] Starting frontend...
start "S&P500 Frontend" cmd /k "cd frontend && npm install --prefer-offline && npm run dev"

echo Done. Check the two new windows.
