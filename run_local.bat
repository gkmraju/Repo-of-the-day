@echo off
SETLOCAL
echo ================================================
echo   Repo Of The Day -- Local Test Run
echo ================================================
echo.

cd /d "%~dp0"

:: Check .env exists
if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Please create .env from .env.example and fill in your tokens.
    pause
    exit /b 1
)

:: Install / upgrade dependencies
echo [1/4] Installing dependencies...
pip install -r requirements.txt --quiet
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pip install failed. Is Python/pip in PATH?
    pause
    exit /b 1
)
echo       Done.

:: Download NLTK data
echo [2/4] Downloading NLTK data...
python -c "import nltk; [nltk.download(p, quiet=True) for p in ['punkt','punkt_tab','stopwords','averaged_perceptron_tagger']]"
echo       Done.

:: Run the app (posts to Telegram for real)
echo [3/4] Running Repo Of The Day...
echo       (This will post to your Telegram channel)
echo.
python app.py --verbose

echo.
echo [4/4] Run complete. Check your Telegram channel!
echo.
pause
