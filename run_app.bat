@echo off
title Trading Strategy and Screening Parameters
cd /d "%~dp0"

echo ========================================================
echo   Trading Strategy and Screening Parameters Dashboard
echo ========================================================
echo.
echo Starting Streamlit server...
echo The dashboard will automatically open in your web browser.
echo Press Ctrl + C to stop the server.
echo.

python -m streamlit run app.py --server.headless false %*

pause
