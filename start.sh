#!/bin/bash

# SYRAA Clinic AI Receptionist - Startup Script

echo "🏥 Starting SYRAA Clinic AI Receptionist..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "📝 Please copy .env.example to .env and configure your settings"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Start MCP Server in background
echo "🚀 Starting MCP Server..."
uvicorn mcp_server:app --host 0.0.0.0 --port 8000 &
MCP_PID=$!

# Wait a moment for server to start
sleep 3

# Check if MCP server is running
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ MCP Server is running on http://localhost:8000"
    echo "📚 API Documentation: http://localhost:8000/docs"
else
    echo "❌ MCP Server failed to start"
    exit 1
fi

# Start Agent
echo "🤖 Starting Voice Agent..."
python agent.py

# Cleanup on exit
trap "kill $MCP_PID" EXIT