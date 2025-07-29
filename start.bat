@echo off
REM SYRAA Clinic AI Receptionist - Windows Startup Script

echo 🏥 Starting SYRAA Clinic AI Receptionist...

REM Check if .env file exists
if not exist .env (
    echo ❌ Error: .env file not found!
    echo 📝 Please copy .env.example to .env and configure your settings
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist .venv (
    echo 📦 Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call .venv\Scripts\activate

REM Install dependencies
echo 📥 Installing dependencies...
pip install -r requirements.txt

REM Start MCP Server in background
echo 🚀 Starting MCP Server...
start /b uvicorn mcp_server:app --host 0.0.0.0 --port 8000

REM Wait a moment for server to start
timeout /t 3 /nobreak > nul

REM Check if MCP server is running
curl -f http://localhost:8000/health > nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ MCP Server is running on http://localhost:8000
    echo 📚 API Documentation: http://localhost:8000/docs
) else (
    echo ❌ MCP Server failed to start
    pause
    exit /b 1
)

REM Start Agent
echo 🤖 Starting Voice Agent...
python agent.py

pause