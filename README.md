# 🚀 Repo Of The Day

> **Automatically discover, analyse, and publish the best GitHub repository of the day to your Telegram channel — every day at 9 PM IST. 100% free, zero cloud AI, runs entirely on GitHub Actions.**

---

## ✨ What It Does

Every day at **9:00 PM IST** the bot:

1. **Discovers** repos from GitHub Trending, Search API, and Topic feeds
2. **Scores** each repo with a 9-signal weighted algorithm
3. **Skips** anything already posted (persistent history)
4. **Analyses** the winner using local NLP (no paid AI)
5. **Generates** a professional educational summary (12 structured sections)
6. **Creates** a 1280×720 dark-theme thumbnail with Pillow
7. **Posts** thumbnail + formatted message to your Telegram channel
8. **Commits** the updated history back to the repo automatically

---

## 📸 Example Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 REPO OF THE DAY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 Repository: fastapi/fastapi
⭐ Stars: 73.2k  ⭐ Legendary
💻 Language: Python
👤 Author: tiangolo
📜 License: MIT
🏷️  #api  #python  #fastapi  #rest  #openapi

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📖 What is it?
...
```

---

## 🏗️ Architecture

```
repo_of_the_day/
├── app.py                        # Main orchestrator & CLI
├── config.py                     # Pydantic-settings config
├── requirements.txt
├── .env.example
│
├── services/
│   ├── github_service.py         # Multi-source repo discovery
│   ├── repository_ranker.py      # 9-signal scoring algorithm
│   ├── repository_analyzer.py    # Full analysis pipeline
│   ├── readme_parser.py          # Structured README extraction
│   ├── summarizer.py             # Local NLP (TextRank, TF-IDF, RAKE)
│   ├── image_generator.py        # Pillow 1280×720 thumbnail
│   ├── markdown_formatter.py     # Telegram MarkdownV2 formatter
│   ├── telegram_service.py       # Bot API client with retry
│   ├── storage.py                # JSON history management
│   ├── logger.py                 # Loguru configuration
│   └── utils.py                  # Shared utilities
│
├── templates/
│   ├── telegram_template.jinja2  # Message template
│   └── html_report.jinja2        # Daily HTML report
│
├── assets/                       # Generated thumbnails
├── data/
│   ├── sent_repositories.json    # Posting history
│   └── repository_cache.json     # Discovery cache
├── reports/                      # Daily HTML reports
├── logs/                         # Rotating log files
│
└── .github/
    └── workflows/
        └── daily.yml             # GitHub Actions workflow
```

---

## ⚙️ Scoring Algorithm

| Signal | Weight | Description |
|---|---|---|
| Stars | 25% | Log-normalised star count |
| Recent Activity | 20% | Days since last push (inverted) |
| Growth Potential | 10% | Fork-to-star ratio |
| README Quality | 10% | Length + key section presence |
| Contributors | 10% | Log-normalised contributor count |
| Documentation | 10% | Homepage, topics, license |
| Issue Activity | 5% | Engagement signal |
| Popularity | 5% | Watcher count |
| Community | 5% | Contributor-to-star ratio |

All weights are configurable via environment variables.

---

## 🛠 Tech Stack

| Category | Library |
|---|---|
| GitHub API | PyGithub, httpx |
| HTML Parsing | beautifulsoup4, lxml |
| NLP | NLTK, sumy (TextRank/LexRank), scikit-learn (TF-IDF) |
| Image Generation | Pillow |
| Templating | Jinja2 |
| Telegram | requests (direct Bot API) |
| Config | pydantic-settings |
| Logging | Loguru |
| Data | orjson, pandas |

**Zero paid AI APIs used.**

---

## 🚀 Quick Start

### 1. Fork & Clone

```bash
git clone https://github.com/YOUR_USERNAME/repo-of-the-day.git
cd repo-of-the-day
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and fill in your tokens
```

### 4. Test Locally

```bash
# Dry-run: generates everything but skips Telegram
python app.py --dry-run

# Analyse a specific repo
python app.py --force tiangolo/fastapi --dry-run

# Check posting stats
python app.py --stats
```

---

## 🔐 GitHub Actions Setup

### Step 1 — Add Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Value |
|---|---|
| `GITHUB_TOKEN` | Auto-provided by GitHub Actions (no action needed) |
| `TELEGRAM_BOT_TOKEN` | Your bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your channel ID (e.g. `@mychannel` or `-100123456`) |

> **Note:** `GITHUB_TOKEN` is automatically injected by GitHub Actions. You only need to add the Telegram secrets.

### Step 2 — Enable Workflow Permissions

Go to **Settings** → **Actions** → **General** → **Workflow permissions** → select **Read and write permissions**.

This is required so the workflow can commit the updated history JSON back to the repo.

### Step 3 — Push to GitHub

```bash
git add .
git commit -m "feat: initial repo-of-the-day setup"
git push
```

The workflow will run automatically every day at **9:00 PM IST (15:30 UTC)**.

### Manual Trigger

Go to **Actions** → **Repo Of The Day — Daily Post** → **Run workflow**

Options:
- **Dry run** — generate content but skip Telegram posting
- **Force repo** — specify `owner/repo` to analyse a specific repository

---

## 🤖 Telegram Bot Setup

1. Open Telegram and message **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the bot token (format: `123456789:ABC...`)
4. Add your bot as an **admin** to your channel
5. Get your channel ID:
   - For public channels: `@channelname`
   - For private channels: forward a message to [@userinfobot](https://t.me/userinfobot) to get the numeric ID

---

## ⚙️ Configuration Reference

All settings can be set via `.env` or environment variables:

| Variable | Default | Description |
|---|---|---|
| `GITHUB_TOKEN` | **required** | GitHub Personal Access Token |
| `TELEGRAM_BOT_TOKEN` | **required** | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | **required** | Channel/Group Chat ID |
| `DRY_RUN` | `false` | Skip Telegram posting |
| `MIN_STARS` | `300` | Minimum star threshold |
| `WEIGHT_STARS` | `0.25` | Scoring weight for stars |
| `WEIGHT_RECENT_ACTIVITY` | `0.20` | Scoring weight for recency |
| `WEIGHT_README_QUALITY` | `0.10` | Scoring weight for README |
| `MAX_REPOS_PER_SOURCE` | `50` | Discovery limit per source |

---

## 📊 Discovery Sources

| Priority | Source | Method |
|---|---|---|
| 1 | GitHub Trending | Web scrape (no API key needed) |
| 2 | GitHub Search API | `stars:>N pushed:>date` queries |
| 3 | GitHub Topics | Popular topic feeds |

Filters applied:
- Not archived
- Not a fork
- ≥ 300 stars (configurable)
- Updated recently
- Not already posted

---

## 🧠 NLP Analysis (No Paid AI)

All text analysis is done locally using:

| Technique | Library | Purpose |
|---|---|---|
| TextRank | sumy | Extractive summarisation |
| TF-IDF | scikit-learn | Keyword extraction |
| Tokenisation | NLTK | Sentence splitting |
| Pattern matching | re, custom | Section detection |
| Template generation | Jinja2 | Structured content |

No OpenAI, Gemini, Claude, or any cloud AI service is used.

---

## 🖼️ Thumbnail Spec

- **Resolution:** 1280 × 720 px
- **Theme:** Dark GitHub-inspired
- **Elements:** Repo name, owner, stars, language badge, topic pills, key features, score bar, date, URL

---

## 📋 CLI Reference

```bash
python app.py                          # Normal run
python app.py --dry-run                # Skip Telegram
python app.py --force owner/repo       # Force specific repo
python app.py --force owner/repo --dry-run
python app.py --stats                  # Posting history
python app.py --clear-cache            # Reset discovery cache
python app.py --verbose                # DEBUG logging
```

---

## 🗂️ Data Files

| File | Purpose |
|---|---|
| `data/sent_repositories.json` | Persistent posting history (never repeat) |
| `data/repository_cache.json` | Discovery cache (cleared manually) |
| `reports/YYYY-MM-DD_*.html` | Daily HTML reports |
| `assets/*_thumbnail.png` | Generated thumbnails |
| `logs/repo_of_the_day_*.log` | Rotating daily logs |

---

## 🛣️ Roadmap

- [ ] SQLite history backend (for large history)
- [ ] Weekly analytics digest
- [ ] Interactive Telegram buttons (Star, Open, Share)
- [ ] CSV/JSON export of history
- [ ] Category detection (Security, ML, DevOps, etc.)
- [ ] Beginner-friendliness score
- [ ] GitHub Pages automated report site
- [ ] Docker support
- [ ] Unit tests

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Commit your changes with conventional commits
4. Push and open a Pull Request

Please keep all contributions free of paid API dependencies.

---

## 📄 License

MIT License — free for personal and commercial use.

---

## ⭐ Support

If this project helps you, please **star the repository** and **share it** with your developer community!

---

*Built with ❤️ — 100% free, open source, and automated.*
