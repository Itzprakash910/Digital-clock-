# ConnectMate MongoDB Setup

1. Create a free MongoDB Atlas cluster.
2. Create database user and allow the deployment IP/network required by your host.
3. Copy the connection string to `MONGODB_URI`.
4. Set `MONGODB_DB=connectmate` and `DATABASE_BACKEND=mongo`.
5. Start the bot. Collections and indexes are created automatically:
   `users`, `swipes`, `profile_posts`, `profile_views`, `ratings`, `contacts`,
   `chat_sessions`, `chat_messages`, `payments`, `reports`, `broadcasts`, `admin_logs`.
6. MongoDB persists users, profiles, posts, matches, chats, referrals, coins and Premium state across bot restarts.

Do not commit the URI or bot token.
