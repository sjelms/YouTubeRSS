# YouTubeRSS

A Python tool for exporting YouTube playlist data into multiple research-friendly formats (JSON, CSV, Markdown, RSS).  
This project helps researchers collect, search, and review saved videos without being locked into YouTube’s interface.

## ✨ Features
- Export metadata from any YouTube playlist
- Save results as:
  - JSON (raw metadata)
  - CSV (spreadsheet-friendly)
  - Markdown (for Obsidian/notes)
  - RSS feed (for feed readers)
- Local-first: manage your own exports without third-party services

## 🛠 Installation
Clone the repo and set up a Python virtual environment:

```bash
git clone https://github.com/sjelms/YouTubeRSS
cd YouTubeRSS
python -m venv .venv
source .venv/bin/activate  # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
```

## 🚀 Usage
Run the export script with a playlist URL or ID:

```bash
python src/export.py "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID"
```

Outputs will be stored in the `data/` folder.

## 📍 Roadmap
- [ ] Export JSON metadata
- [ ] Export CSV format
- [ ] Export RSS feed
- [ ] Export Markdown notes
- [ ] Add CLI options (choose output format)
- [ ] Add support for multiple playlists in one run

