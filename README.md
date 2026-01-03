# Gaming News Telegram Bot

A Python-based Telegram bot that scrapes the latest gaming news from **GameRant** and automatically posts updates to a Telegram channel with formatted captions and optional banner-composited images.

Designed to run via cron or GitHub Actions with duplicate prevention and retry handling.

---

## ✨ Features

- Scrapes latest gaming news from GameRant
- Posts news to Telegram with clean HTML formatting
- Optional image posting with banner overlay (Pillow)
- Duplicate post prevention using JSON storage
- Timezone-aware date filtering (Asia/Kolkata)
- Async Telegram posting
- Retry logic for network and Telegram failures
- Can fallback to text-only posts if image fails

---

## ⚙️ Requirements

- Python 3.9+
- Telegram Bot Token
- Telegram Channel / Group ID

---

## 📦 Installation

```bash
pip install -r requirements.txt 
