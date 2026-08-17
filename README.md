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
   python -m src.bot.main

The bot will start polling and be ready for use.

Project Structure
senseirenderbot/
├── src/                     # Source code
│   ├── bot/                 # Main bot code (aiogram)
│   │   ├── handlers/        # Command and event handlers
│   │   ├── middlewares/     # Custom middleware
│   │   ├── states/          # FSM states
│   │   ├── keyboards/       # Keyboards
│   │   ├── db.py            # MongoDB initialization
│   │   └── main.py          # Entry point
│   ├── core/                # Core: config, DI container, providers
│   ├── infra/               # Infrastructure layers (MongoDB)
│   ├── services/            # Business logic (games, economy, etc.)
│   ├── domain/              # Domain models and resources
│   └── texts/               # Localizable strings and phrases
├── scripts/                 # Helper scripts (seed, cleanup, etc.)
├── .env.example             # Example environment variables file
├── docker-compose.yml       # Configuration to run MongoDB (and optionally other services)
├── Dockerfile               # Official production image
├── README.md                # This file
├── requirements.txt         # Python dependencies
   .github/
       workflows/
           ci.yml           # GitHub Actions CI (run tests on push)

Available Scripts
- scripts/seed_data.py – populates database with initial data (users, achievements, etc.)
- scripts/verify_deletion.py – verifies correct deletion of users
- scripts/delete_users.py – deletes test users (as needed)

Bot Commands
The bot includes various commands for users and administrators. Key commands include:
- /start - Launch the bot
- /help - Show help
- /profile - View your profile
- /top - View leaderboard
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