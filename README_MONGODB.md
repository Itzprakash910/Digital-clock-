# MongoDB setup (recommended production database)

## 1. MongoDB Atlas account
1. `https://www.mongodb.com/atlas` par free account banayein.
2. **Create / Build Database** → free tier cluster choose karein.
3. **Database Access** me ek database user banayein (strong password).
4. **Network Access** me apne server/VPS ka IP allow karein. Temporary testing ke liye `0.0.0.0/0` use kiya ja sakta hai, lekin production me IP restrict karna better hai.
5. **Connect → Drivers → Python** se `mongodb+srv://...` URI copy karein.

## 2. Bot `.env`
```env
DATABASE_BACKEND=mongo
MONGODB_URI=mongodb+srv://USERNAME:PASSWORD@CLUSTER.mongodb.net/?retryWrites=true&w=majority
MONGODB_DB=tele_tinder
```
`BOT_TOKEN`, `ADMIN_IDS`, `PAYMENT_PROVIDER_TOKEN` etc. bhi set karein.

**URI ko GitHub/public code me kabhi commit na karein.**

## 3. Install & run
```bash
python -m pip install -r requirements.txt
python bot.py
```
Startup par bot MongoDB ko `ping` karega aur indexes automatically create karega.

## 4. Existing SQLite data migrate karna
Agar pehle `tele_tinder.db` me users hain:
```bash
python migrate_sqlite_to_mongo.py tele_tinder.db
```
Migration users, swipes, reports, payments, broadcasts aur engagement counters ko MongoDB me copy karti hai.

## 5. Data design
- `users`: complete profile + private contacts
- `swipes`: likes/super/pass
- `profile_views`: profile-view analytics
- `ratings`: 1–5 ratings
- `payments`: Premium payments
- `reports`: safety reports
- `broadcasts`: admin campaigns
- `chats`: future chat metadata
- `admin_logs`: future audit trail

Phone/social data `users.contacts` ke private section me rehta hai. Application contacts ko **Premium + mutual match** ke bina show nahi karti. Normal users in-bot chat use karte hain.

## 6. Backups
Atlas me automated backups/backup options plan ke hisab se enable karein. Production me regular backup aur restore test zaroor karein.
