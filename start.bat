@echo off
setlocal
set ROOT=%~dp0

echo Checking ports...
netstat -ano | findstr /R /C:":8001 .*LISTENING" >nul
if %ERRORLEVEL%==0 (
  echo [skip] API already listening on :8001
) else (
  echo [1/2] Starting blog API on :8001 ...
  start "Zeej API" cmd /k "cd /d %ROOT%backend && .venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8001"
  timeout /t 2 /nobreak >nul
)

netstat -ano | findstr /R /C:":5180 .*LISTENING" >nul
if %ERRORLEVEL%==0 (
  echo [skip] Frontend already listening on :5180
) else (
  echo [2/2] Starting blog frontend on :5180 ...
  start "Zeej Web" cmd /k "cd /d %ROOT% && npm run dev -- --port 5180 --strictPort"
)

echo.
echo Open: http://localhost:5180/
echo Admin email / password: see backend\.env  ^(ADMIN_EMAIL / ADMIN_PASSWORD^)
echo Invite: ZEEJ-WELCOME
echo.
pause
