# 🎮 Twitch Vote Tracker Bot 🚀

A powerful async Twitch bot that tracks channel point redemptions for game voting, updates Google Sheets in real-time, and engages your chat with live updates! 🔥

---

## 🌟 Features

- 🎉 Tracks **Normal Votes** and **Super Votes** (weighted votes)
- 🔍 Fuzzy matching for game name detection (handles typos!)
- 📊 Automatic **Google Sheets integration** with live sorting
- 💬 Dynamic chat notifications with vote rankings
- 🔄 **Async architecture** for high performance
- 🔒 Secure **OAuth2 token management** with auto-renewal
- 🛠️ Easy configuration via JSON files

---

## 📋 Prerequisites

- 🐍 Python 3.9+
- 📦 Required Python packages:
  - `aiohttp`
  - `gspread`
  - `fuzzywuzzy`
  - `pandas`
- 📝 Twitch Developer Account (with 2 applications)
- 🖥️ Google Cloud Project with **Sheets API** enabled
- 📄 Google Service Account JSON credentials

---

## 🚀 Installation

### Clone repository:

```bash
git clone https://github.com/yourusername/twitch-vote-bot.git
cd twitch-vote-bot
