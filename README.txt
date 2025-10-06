
RS Like Bot - Final Optimized Version (Render Ready)
- /start, /help, /like commands
- Colorful animated loading screen
- Environment variable support (BOT_TOKEN, LIKE_API_URL, API_KEY, ALLOWED_GROUP)
- Flask ping server for uptime monitoring
- Only allowed group (-1002892874648)

Deploy steps:
1. Push to GitHub
2. Create a Render Web Service connected to repo
3. Set environment variables on Render
4. Build: pip install -r requirements.txt
5. Start: python main.py
6. Use UptimeRobot to ping "/" to prevent sleep
