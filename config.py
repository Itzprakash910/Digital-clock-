import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "dateswipe_bot")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DB_PATH = os.getenv("DB_PATH", "tele_tinder.db")

CURRENCY = "MDL"  # Moldovan Leu (amount smallest unit = bani, 1 MDL = 100)

# price = bani (4900 = 49.00 MDL). Telegram ka minimum amount check kar lein.
PLANS = {
    "week":    {"title": "Premium 7 Days",  "days": 7,  "price": 4900,  "coins": 300},
    "month":   {"title": "Premium 30 Days", "days": 30, "price": 14900, "coins": 900},
    "quarter": {"title": "Premium 90 Days", "days": 90, "price": 34900, "coins": 2200},
}

# Limits
FREE_LIKES_PER_DAY = 30
FREE_SUPER_PER_DAY = 1
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
