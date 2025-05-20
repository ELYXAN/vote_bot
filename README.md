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
Install dependencies:
bash
Kopieren
Bearbeiten
pip install aiohttp gspread pandas fuzzywuzzy python-Levenshtein
Set up configuration files:
Rename Vote tracking.json.example to Vote tracking.json and add your Google credentials

Configure config.json with your Twitch and Google Sheets details

⚙️ Configuration
🔧 config.json Setup
json
Kopieren
Bearbeiten
{
    "streamer": {
        "client_id": "YOUR_STREAMER_CLIENT_ID",
        "client_secret": "YOUR_STREAMER_SECRET",
        "scopes": "channel:read:redemptions channel:manage:redemptions"
    },
    "chat_bot": {
        "client_id": "YOUR_BOT_CLIENT_ID",
        "client_secret": "YOUR_BOT_SECRET",
        "scopes": "chat:read chat:edit"
    },
    "spreadsheet_id": "YOUR_GOOGLE_SHEET_ID",
    "rewards": {
        "normal_vote": "YOUR_NORMAL_VOTE_ID",
        "super_vote": "YOUR_SUPER_VOTE_ID"
    }
}
📊 Google Sheets Setup
Create a sheet with columns:

A: Votes (numeric)

B: Game (text)

Share the sheet with your service account email

Enable Google Sheets API in your Cloud Console

🎮 Usage
Run the bot:

bash
Kopieren
Bearbeiten
python vote_bot_3.0.py
Follow OAuth instructions in your browser when prompted 🌐

Let viewers redeem votes! The bot will:

✅ Auto-process redemptions

📈 Update vote counts

🔄 Sort the sheet automatically

💬 Post chat notifications

📌 Example Workflow
Viewer redeems "Super Vote" for "Minceraft"

Bot detects "Minecraft" via fuzzy matching (85% match) 🎯

Adds 10 votes (super vote weight)

Updates Google Sheets and posts in chat:

css
Kopieren
Bearbeiten
@User voted for Minecraft! | Votes: 42 | New position: #3
💡 Pro Tips
🛡️ Keep your config.json and service account file secure!

🔄 Use !votes command to trigger manual sheet refresh

📈 Set different weights for vote types in config

🧹 Regularly check inacurate_games.csv for typos

⚠️ Troubleshooting
🔑 Authentication Issues: Delete tokens from config.json and re-authenticate

📊 Sheet Connection Problems: Verify sharing permissions on Google Sheet

💬 Chat Errors: Ensure bot has moderator privileges in your channel

🐛 Unexpected Behavior: Check Vote_IDs.csv for duplicate entries

👏 Credits
Developed with ❤️ by ELYXAN / KUS_SWAT_

Special thanks to the Twitch API community 📚

📜 License
MIT License - Feel free to modify and distribute! 🎉

rust
Kopieren
Bearbeiten

If you'd like, I can generate this as a downloadable `README.md` fi
### Clone repository:

```bash
git clone https://github.com/yourusername/twitch-vote-bot.git
cd twitch-vote-bot
