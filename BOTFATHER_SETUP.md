# ConnectMate — BotFather Setup

1. Create the bot with @BotFather and copy the token to `BOT_TOKEN`.
2. Set the username in `BOT_USERNAME` without `@`.
3. Set `/setname` to **ConnectMate**.
4. Set `/setdescription` using the long description from `.env.example`.
5. Set `/setabouttext` to:
   `💘 Real People • Nearby • Safe • Match • Chat • Connect`
6. Upload `assets/connectmate_description.png` as the bot profile/description image where Telegram's BotFather/client UI supports it.
7. Run the bot once; it also tries to set name/short/full description through Bot API.
8. For payments, configure a Telegram-supported payment provider token. For production, test successful_payment and refunds/webhook/payment-provider settings before launch.
9. Keep `BOT_TOKEN`, `MONGODB_URI`, payment token and admin IDs private.

Recommended commands are registered automatically at startup.
