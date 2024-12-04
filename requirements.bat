@echo off

rem Install npm packages
echo Installing npm packages...
timeout /t 3 > nul
start cmd.exe /c "npm install && npm run build && winget install Gyan.FFmpeg && pip install -r requirements.txt && copy .env.example .env"