# India Job Updates - Telegram Bot Pipeline

Automated Telegram Bot for posting Fresher, Internship, Walk-in, IT/Non-IT, and Government job alerts to [@indiajobupdates_official](https://t.me/indiajobupdates_official).

---

## 📁 Project Structure

```
JOB_BOT/
├── .github/
│   └── workflows/
│       └── jobs.yml           # GitHub Actions workflow (runs every 2 hours)
├── .env.example               # Environment variables template
├── .gitignore                 # Files excluded from git
├── job_bot.py                 # Core automation script
├── requirements.txt           # Python dependencies
├── seen.json                  # Deduplication tracker (auto-updated by GitHub Actions)
├── sources.json               # Configured job search queries and RSS feeds
└── README.md                  # Setup & usage documentation
```

---

## 🚀 Setup & Deployment Steps

### 1. GitHub Repository
Repository: [https://github.com/Jaaveed786/job-alert-bot](https://github.com/Jaaveed786/job-alert-bot)

Upload the contents of this folder (`D:\Telegram_Channel_Bot\JOB_BOT`) to your GitHub repository, keeping the `.github/workflows/jobs.yml` structure intact.

### 2. Configure GitHub Secrets
In your GitHub repo, go to **Settings** > **Secrets and variables** > **Actions** > **New repository secret**, and add:

| Secret Name | Value | Description |
|---|---|---|
| `BOT_TOKEN` | `...` | Token received from [@BotFather](https://t.me/BotFather) on Telegram |
| `ADZUNA_APP_ID` | `679e682e` | Adzuna Application ID |
| `ADZUNA_APP_KEY` | `bc4871c6f9b490717e2a8b082f555b69` | Adzuna Application Key |

### 3. Telegram Channel Permissions
1. Open your channel [@indiajobupdates_official](https://t.me/indiajobupdates_official).
2. Go to **Channel Settings** > **Administrators** > **Add Administrator**.
3. Search for your bot username and add it.
4. Enable the **"Post Messages"** permission.

### 4. Run & Verify
1. Go to the **Actions** tab in your GitHub repository.
2. Under All workflows, select **"Post jobs"**.
3. Click **Run workflow** > **Run workflow**.
4. Check your Telegram channel in 1-2 minutes for new job posts.

---

## ⚙️ How It Works

1. **Fetch**: Fetches new job listings from the Adzuna API and enabled RSS feeds in `sources.json`.
2. **Dedupe**: Compares job URL hashes against `seen.json` to prevent reposting duplicates.
3. **Classify**: Categorizes each job (`#Fresher`, `#Internship`, `#WalkIn`, `#Govt`, `#Experienced`, `#IT`, `#NonIT`).
4. **Format**: Generates clean HTML message formats with title, company, location, apply links, hashtags, and anti-scam warnings.
5. **Post**: Sends posts via Telegram Bot API with rate limiting (max 8 jobs per run, every 2 hours).
6. **Persist**: Automatically commits updated `seen.json` back to the GitHub repository.

---

## 🔍 Adding Govt & RSS Feeds (`sources.json`)
To enable government or local walk-in notifications:
1. Create a Google Alert (e.g. *"govt recruitment notification"* or *"walk-in drive Bengaluru"*) with delivery set to **RSS feed**.
2. Open `sources.json`, paste the feed URL into the `url` field, and set `"enabled": true`.
