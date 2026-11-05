#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo " Starting Multi-Agent Agentic Commerce Platform (FastAPI) "
echo " Powered by LangGraph, Groq, Razorpay, and SQLite         "
echo "=========================================================="

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install langgraph langchain langchain-groq langchain-core fastapi uvicorn razorpay pydantic python-dotenv requests
fi

echo "Starting server on http://localhost:8000 ..."
.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
