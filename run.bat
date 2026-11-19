@echo off
rem Start the development server on Windows (expects a virtual environment in venv\ or .venv\).
title Kontor CRM
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    call venv\Scripts\activate.bat
)
alembic upgrade head
uvicorn main:app --reload
