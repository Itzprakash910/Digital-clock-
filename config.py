import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "dateswipe_bot")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
MONGODB_DB = os.getenv("MONGODB_DB", "tele_tinder")
DATABASE_BACKEND = os.getenv("DATABASE_BACKEND", "mongo").strip().lower()
DB_PATH = os.getenv("DB_PATH", "tele_tinder.db")

PRICE_SYMBOL = os.getenv("PRICE_SYMBOL", "₹")
NOTIFY_NEW_USERS = os.getenv("NOTIFY_NEW_USERS", "1") == "1"
START_DELAY = int(os.getenv("START_DELAY", "20"))

CURRENCY = os.getenv("CURRENCY", "INR").upper()

# price = bani (4900 = 49.00 MDL). Telegram ka minimum amount check kar lein.
PLANS = {
    "week":    {"title": "Premium 7 Days",  "days": 7,  "price": 4900,  "coins": 300},
    "month":   {"title": "Premium 30 Days", "days": 30, "price": 14900, "coins": 900},
    "quarter": {"title": "Premium 90 Days", "days": 90, "price": 34900, "coins": 2200},
}

FREE_LIKES_PER_DAY = 30
FREE_SUPER_PER_DAY = 1
FREE_CHAT_STARTS_PER_DAY = int(os.getenv("FREE_CHAT_STARTS_PER_DAY", "3"))
MAX_PROFILE_POSTS = int(os.getenv("MAX_PROFILE_POSTS", "4"))
PREMIUM_SUPER_PER_DAY = 10
REFERRAL_COINS = 10
BOOST_COST_COINS = 40
BOOST_MINUTES = 30
DAILY_BASE_COINS = 5

INTERESTS = ["🎵 Music", "🎬 Movies", "✈️ Travel", "📚 Books", "🏋️ Fitness", "🎮 Gaming",
             "🍳 Cooking", "📸 Photography", "💻 Tech", "🎨 Art", "🏍️ Biking", "🐶 Pets",
             "☕ Coffee", "🌿 Nature", "🏏 Cricket", "💃 Dance"]

MOODS = ["😎 Chill", "🎉 Party", "🎧 Music", "☕ Coffee date", "🚗 Adventure",
         "📚 Study buddy", "💬 Just chat"]

ICEBREAKERS = [
    "Agar kal chhutti mile to aap kya karenge?",
    "Aapki sabse favourite late-night food kya hai?",
    "Ek cheez jo aapko 5 min mein khush kar de?",
    "Dream trip kahan ki hai?",
    "Aapka guilty-pleasure song kaunsa hai?",
    "Chai ya coffee, aur kyun?",
]
