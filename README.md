# ConnectMate 💘

A Telegram dating/matching bot built on the supplied Digital-clock-main project structure, upgraded into a complete ConnectMate experience.

## Core features
- 18+ onboarding: age, gender, looking-for, bio, interests, photo and optional location.
- Nearby-first smart discovery, age/distance/online filters.
- Like / Pass / Super Like, mutual match and Who Liked Me.
- Profile views, ratings, mood and icebreakers.
- Up to 4 additional profile posts with captions.
- Mutual-match private relay chat; text/photo/video/voice relay.
- Free users: 3 new chat starts per rolling 24-hour window; existing matched chats can continue.
- Premium: unlimited new chats, unlimited likes, Super Likes, Who Liked Me, rewind, more nearby users and contact/social access.
- Phone/Telegram/Instagram/Facebook/other contact fields are private and shown only to Premium mutual matches when the owner enables them.
- Referral deep-link rewards and coins.
- Daily rewards and profile boost.
- Admin dashboard, reports, ban/verify, VIP grant/revoke, broadcasts, CSV export and statistics.
- MongoDB Atlas production backend with SQLite fallback for local development.

## Run
```bash
python -m venv .venv
# activate it
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

Set `DATABASE_BACKEND=mongo` and a valid `MONGODB_URI` for persistent production storage.

## Deploy
Works with a worker/service that can run `python bot.py` and expose `$PORT` (Render/Railway style). MongoDB Atlas is recommended for persistent storage.

## Safety
18+ only. Add Terms/Privacy/Report/Block flows and moderation before public launch. Never put secrets in source control.


## Discovery reliability fixes (v1.1)
- Reciprocal gender/looking-for compatibility is enforced in both SQLite and MongoDB.
- SQLite now includes likes/rating columns required by profile ranking and ratings.
- MongoDB syntax error in the search helper was fixed.
- Discover now has clear empty-state/filter actions.
- Nearby explicitly asks for Telegram location when unavailable.
- Profile gallery buttons are available directly from Discover and Matches.
- `/discover` is now an alias for `/find`.
- MongoDB is selected only when `MONGODB_URI` is configured; otherwise SQLite fallback is used.


## Interaction & notification update (v1.2)
- Chat messages now show the sender's ConnectMate display name.
- Users receive profile activity notifications for unique views, likes, super-likes, skips and ratings.
- One-time achievements unlock for profile views, received likes and ratings, with celebratory messages.
- Matches are fully accessible through page navigation instead of a hard 20-profile cutoff.
- Likes contains both profiles you liked and (for Premium) profiles who liked you.
- Profile Views shows recent unique viewers.
- Contacts & Social setup is available from Profile settings; Telegram username is auto-detected, while phone must be shared/entered by the user.
- Help & Support lets users send a message directly to configured admins; admins can reply from the existing admin message flow.
- Discovery now checks both users' gender and age preferences, plus filters and activity, in SQLite and MongoDB.
- MongoDB like counters no longer double-count repeated/changed swipes.
- Telegram inline buttons do not expose custom background colors through the Bot API; styling is standardized with emojis, concise labels and consistent layouts.
