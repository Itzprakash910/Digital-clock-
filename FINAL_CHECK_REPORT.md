# ConnectMate Final Logic Check — v1.1

## Fixed after live screenshot review
- Discover / Find candidate selection now checks **both sides** of gender/looking-for preferences.
- SQLite discovery no longer uses a random pre-limit that can hide compatible users.
- MongoDB discovery uses the same reciprocal preference rule.
- MongoDB had a duplicate `search_users()` declaration that could cause a syntax error; fixed.
- SQLite was missing `likes_received`, `likes_given`, `rating_avg`, and `rating_count` columns even though ranking/rating code used them; schema migration added them.
- SQLite swipe counters are maintained when likes/super-likes are created, changed, or rewound.
- `/discover` alias added for `/find`.
- `/menu` command added.
- Discover empty-state now offers Filters / Nearby / Discover Again instead of a dead-end message.
- Nearby now explicitly asks for Telegram location when the user has not shared it.
- Nearby empty-state provides Filters / Discover actions.
- Extra profile posts can now be opened directly from Discover and Matches via a Posts button.
- Premium plan buttons now display the configured currency instead of hard-coded MDL.
- MongoDB is selected only when `DATABASE_BACKEND=mongo` **and** `MONGODB_URI` exists; otherwise SQLite is used automatically.
- Matches exclude inactive/blocked profiles in MongoDB as well.

## Static validation
- Python `compileall`: PASS
- Reciprocal discovery SQL simulation: PASS
- Mutual match SQL simulation: PASS
- Callback routes audited: PASS for the current inline-button prefixes.

## Important runtime requirements
- Telegram bot token is required.
- For persistent production data, configure MongoDB Atlas (`MONGODB_URI`) and `DATABASE_BACKEND=mongo`.
- Nearby matching requires users to share Telegram location.
- Premium payment requires a valid Telegram payment provider configuration; otherwise the Premium UI remains visible but payment cannot be completed.
