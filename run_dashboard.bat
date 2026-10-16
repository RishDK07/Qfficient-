@echo off
title Thermodynamic QUBO Microgrid Presentation Portal
echo =====================================================================
echo Starting Thermodynamic QUBO Microgrid Review Dashboard...
echo =====================================================================

cd /d "%~dp0"

IF EXIST ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) ELSE (
    echo [Notice] Virtual environment not found in .venv. Using system Python...
)

echo Launching Streamlit on http://localhost:8501 ...
streamlit run app.py --server.port 8501
pause
