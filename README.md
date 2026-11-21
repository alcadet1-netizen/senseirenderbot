SENSEI ULTIMATE 2.1
Epic Telegram bot for increasing chat activity.

Quick Start
1. Clone the repository
   git clone https://github.com/alcadet1-netizen/senseirenderbot.git
   cd senseirenderbot

2. Install dependencies
   # Recommended to use a virtual environment
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   .\.venv\Scripts\activate    # Windows

   pip install -r requirements.txt

3. Configure environment
   Copy the example config and fill in required values:
   cp .env.example .env
   Edit .env, specifying:
   - BOT_TOKEN – your Telegram bot token (get from @BotFather)
   - MONGO_URI – MongoDB connection string (default mongodb://localhost:27017/sensei)
   - Optional: HF_TOKEN – Hugging Face token for image generation (if used)
   - Other API keys as needed

4. Run the bot
   # Using docker-compose (recommended for development):
   docker-compose up -d

   # Or direct run:
   python -m src.main

The bot will start polling and be ready for use.

Project Structure
senseirenderbot/
├── src/                     # Source code
│   ├── bot/                 # Main bot code (aiogram)
│   │   ├── handlers/        # Command and event handlers
│   │   ├── middlewares/     # Custom middleware
│   │   ├── states/          # FSM states
│   │   ├── keyboards/       # Keyboards
│   │   └── loader.py        # Bot/dispatcher construction
│   ├── core/                # Core: config, DI container, providers
│   ├── infra/               # Infrastructure layers (MongoDB, MTProto, storage)
│   ├── services/            # Business logic (games, economy, etc.)
│   ├── domain/              # Domain models and repositories
│   ├── texts/               # Localizable strings and phrases
│   ├── web/                 # Mini App HTTP apps (dojo, hedgehog, daily_pet)
│   ├── widgets/             # Card/render pipeline
│   └── main.py              # Entry point
├── scripts/                 # Helper scripts (migrations, diagnostics, builds)
├── tests/                   # Unit + integration tests (MongoDB-backed)
├── docs/                    # Engineering audits and design notes
├── .env.example             # Example environment variables file
├── docker-compose.yml       # Configuration to run MongoDB (and optionally other services)
├── Dockerfile               # Official production image
├── README.md                # This file
├── requirements.txt         # Python dependencies
   .github/
       workflows/
           ci.yml           # GitHub Actions CI (run tests on push)

Available Scripts
- scripts/start_test_mongo.py – starts a local test MongoDB replica set (CI)
- scripts/check_widgets.py – validates widget HTML in Telegram's QuickJS sandbox (CI)
- scripts/migrate_comment_campaigns.py – one-time comment-campaign data migration
- scripts/diagnose_emission.py – read-only SenseiCoin accounting diagnostic
- scripts/prepare_emission_correction.py – prepares an emission correction plan
- scripts/benchmark_read_refresh.py – read-refresh I/O benchmark
- scripts/build_sensei_font.py / scripts/build_katana_previews.py – asset builders
- scripts/widget_samples.py – widget visual sample generator
- scripts/migrate_hedgehog_images.py – one-time GridFS image migration
- scripts/deep_check.py – import/integrity check of the src tree

Bot Commands
The bot includes various commands for users and administrators. Key commands include:
- /start - Launch the bot
- /help - Show help
- /profile - View your profile
- /top - View leaderboard
- /dojo — майнер SenseiCoin в личке бота. [Правила, запуск и проверка перед релизом](docs/DOJO_MINER.md).
- /daily - Claim daily bonus
- /trade - Trading interface
- /duel - Challenge to duel
- /senseiboss [hours] - Admin command to launch a boss with specified duration
- /killboss - Admin command to forcibly kill the current boss (no rewards)

Tests
Run tests:
   pytest
CI workflow (.github/workflows/ci.yml) automatically runs tests on each push to main.

Docker
For production, build the image:
   docker build -t sensei-bot:latest .
Run with your MongoDB:
   docker run -d --name sensei-bot \
     --env-file .env \
     sensei-bot:latest
If using docker-compose.yml, simply:
   docker-compose up -d
This will start a container with the bot and a MongoDB service.

Distributable Archive
For easy distribution, an archive sensei-distributive.zip is prepared (not included in the repository as it is a distribution bundle). You can create it yourself:
   git archive --format=zip --output=sensei-distributive.zip HEAD

License
Project is distributed under the MIT License – see LICENSE file if present.

For questions or suggestions – open an Issue or Pull Request. Happy development and may your chat be full of activity!

Widget interface
- /senseiwidget — complete profile and XP leaderboard cards with refresh buttons.
- Current Bot API delivery uses animated GIF + inline buttons (PNG/text fallback), not native messageMediaWidget.
- Widget-profile-1 HTML and official sandbox checks: [docs/WIDGETS.md](docs/WIDGETS.md).
- Enable/disable with WIDGETS_ENABLED=true/false; disable motion with WIDGET_ANIMATIONS_ENABLED=false.

Cards now include per-message light/dark and motion controls, measured text wrapping,
and single-message refresh protection. HTML validation is pinned to widget-sandbox v0.6.0.

/upkatana and «ап катана» now show a compact blade-growth animation for the completed
attempt, with actual before/after lengths, cost, rank and PNG/text fallbacks.

Daily hedgehog native chat widget: see [setup, rules and beta/test limitation](docs/HEDGEHOG_WIDGET.md).
