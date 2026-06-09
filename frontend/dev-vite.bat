@echo off
REM Internal helper · sets PATH to include portable Node, then launches Vite.
REM Called by start.ps1 -Frontend OR directly when launching via Start-Process.

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "NODE_DIR=%PROJECT_ROOT%\.tools\node-v20.18.0-win-x64"
set "PATH=%NODE_DIR%;%PATH%"

cd /d "%SCRIPT_DIR%"
"%NODE_DIR%\node.exe" "%SCRIPT_DIR%node_modules\vite\bin\vite.js" --host 127.0.0.1 --port 5173
