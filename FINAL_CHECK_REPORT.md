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


## v1.2 interaction/notification audit
- Chat relay now includes sender display name.
- Profile view, Like, Super Like, Skip and Rating notifications added.
- View/like engagement achievements added with one-time unlocks.
- Matches shows all mutual matches; Likes shows outgoing likes and premium incoming likes.
- Reciprocal gender + age preference checks applied to SQLite and MongoDB discovery.
- MongoDB swipe counters no longer double-count when changing an existing swipe.
- Contacts/Social guided setup added; Telegram username is auto-detected, phone requires Telegram contact share.
- Help & Support button/command forwards user messages to admins with reply action.
- Main/edit menus deduplicated and labels standardized.
- Telegram Bot API does not support custom inline-button colors; consistent emoji/text styling is used instead.
