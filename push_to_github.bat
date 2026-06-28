@echo off
SETLOCAL
echo ================================================
echo   Repo Of The Day -- Push to GitHub
echo ================================================
echo.

cd /d "%~dp0"

:: Step 1: Remove stale git init if any, start fresh
if exist ".git" (
    echo [INFO] Existing .git folder found -- removing stale lock files...
    if exist ".git\config.lock" del /f /q ".git\config.lock" 2>nul
    if exist ".git\index.lock" del /f /q ".git\index.lock" 2>nul
)

:: Step 2: Init (safe even if already done)
git init
git branch -M main

:: Step 3: Configure user
git config user.name "gkmraju"
git config user.email "hasithashish@gmail.com"

:: Step 4: Add remote (ignore error if already exists)
git remote remove origin 2>nul
git remote add origin https://github.com/gkmraju/Repo-of-the-day.git

:: Step 5: Create .gitignore
(
echo # Python
echo __pycache__/
echo *.py[cod]
echo *.pyo
echo .env
echo venv/
echo .venv/
echo *.egg-info/
echo dist/
echo build/
echo.
echo # Logs
echo logs/
echo *.log
echo.
echo # Generated files
echo assets/*.png
echo reports/*.html
echo.
echo # OS
echo .DS_Store
echo Thumbs.db
echo.
echo # IDE
echo .vscode/
echo .idea/
echo *.suo
) > .gitignore

:: Step 6: Stage everything
echo.
echo [INFO] Staging all files...
git add .
git status

:: Step 7: Commit
echo.
echo [INFO] Creating initial commit...
git commit -m "feat: initial release - Repo Of The Day v1.0

- Multi-source GitHub repo discovery (Trending + Search API + Topics)
- 9-signal weighted scoring algorithm
- Local NLP analysis (TextRank, TF-IDF, NLTK) - zero paid AI
- Pillow 1280x720 dark-theme thumbnail generator
- Telegram MarkdownV2 formatted messages with auto-split
- Persistent JSON history (never repeat a repo)
- GitHub Actions workflow: daily 9PM IST auto-post
- HTML daily report generation
- Full CLI with dry-run and force modes"

:: Step 8: Push
echo.
echo [INFO] Pushing to GitHub...
echo [INFO] (A browser window may open for authentication if not cached)
git push -u origin main

echo.
if %ERRORLEVEL% EQU 0 (
    echo ================================================
    echo   SUCCESS! Project pushed to GitHub.
    echo   https://github.com/gkmraju/Repo-of-the-day
    echo ================================================
) else (
    echo ================================================
    echo   PUSH FAILED. Try one of these:
    echo.
    echo   Option A - GitHub CLI (gh):
    echo     gh auth login
    echo     git push -u origin main
    echo.
    echo   Option B - Personal Access Token:
    echo     git remote set-url origin https://YOUR_TOKEN@github.com/gkmraju/Repo-of-the-day.git
    echo     git push -u origin main
    echo ================================================
)

echo.
pause
