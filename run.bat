@echo off
title RAG-Powered Website Chatbot Launcher
echo ==========================================================
echo Starting RAG-Powered Website Chatbot Environment Setup
echo ==========================================================

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.10+ and check 'Add Python to PATH'.
    pause
    exit /b 1
)

:: Create virtual environment if it does not exist
if not exist .venv (
    echo Creating Python virtual environment (.venv)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

:: Install/Upgrade dependencies
echo Installing/upgrading dependencies from requirements.txt...
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo ==========================================================
echo Setup complete! Starting server and opening chatbot...
echo ==========================================================

:: Start browser in background
start http://127.0.0.1:8000/

:: Launch backend server
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
if %errorlevel% neq 0 (
    echo [ERROR] Server terminated with an error.
    pause
)
