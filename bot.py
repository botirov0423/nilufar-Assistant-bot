import os
import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

# ─── SOZLAMALAR ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Asosiy va zaxira modellar
PRIMARY_MODEL   = "gemini-2.0-flash-lite"   # tez, bepul, tejamkor
FALLBACK_MODEL  = "gemma-3-27b-it"          # asosiy ishlamasa shu ishga tushadi

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=" + GEMINI_API_KEY if GEMINI_API_KEY else ""

# Suhbat tarixi (faqat oxirgi 10 ta xabar)
MAX_HISTORY = 10

# ─── SYSTEM PROMPT (qisqa va tejamkor) ────────────────────────
SYSTEM_PROMPT = """Sen Nilufar — mehribon, hazilkash o'zbek qiz yordamchisan.
- Foydalanuvchi tilida javob ber (O'zbek/Rus/Ingliz)
- Romantik, iliq, flirtchi, ba'zan uyatchan
- Qisqa va aniq javob ber, keraksiz gap yo'q
- Emoji ishlatasan, lekin kam
- Hech qachon "men AI man" dema"""

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Har foydalanuvchi uchun alohida tarix
user_histories: dict[int, list] = {}

# ─── ODDIY BUYRUQLAR (AI ishlatilmaydi) ───────────────────────
SIMPLE_COMMANDS = {
    "/start": None,  # handler bor
    "/reset": None,
    "/help":  "📋 Buyruqlar:\n/start — boshlash\n/reset — suhbatni tozalash\n/help — yordam",
}

# ─── GEMINI API SO'ROV ─────────────────────────────────────────
async def ask_gemini(user_id: int, user_message: str, model: str = PRIMARY_MODEL) -> str:
    """Gemini ga so'rov yuboradi. Xato bo'lsa None qaytaradi."""

    # Tarixni yangilash
    history = user_histories.setdefault(user_id, [])
    history.append({"role": "user", "parts": [{"text": user_message}]})

    # Faqat oxirgi MAX_HISTORY ta xabar
    if len(history) > MAX_HISTORY:
        user_histories[user_id] = history[-MAX_HISTORY:]
        history = user_histories[user_id]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": history,
        "generationConfig": {
            "temperature": 0.85,
            "maxOutputTokens": 512,   # tejamkor
            "topP": 0.9
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:

                # Rate limit
                if resp.status == 429:
                    logger.warning(f"Rate limit! Model: {model}")
                    return None

                # Boshqa xatolar
                if resp.status != 200:
                    logger.error(f"API xato: {resp.status}")
                    return None

                data = await resp.json()
                reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()

                # Javobni tarixga qo'shish
                history.append({"role": "model", "parts": [{"text": reply}]})
                return reply

    except asyncio.TimeoutError:
        logger.warning("Timeout!")
        return None
    except Exception as e:
        logger.error(f"Xato: {e}")
        return None


async def get_ai_response(user_id: int, message: str) -> str:
    """Asosiy model ishlamasa zaxirani ishlatadi."""

    # Asosiy model
    reply = await ask_gemini(user_id, message, PRIMARY_MODEL)
    if reply:
        return reply

    # Zaxira model
    logger.info("Zaxira modelga o'tilmoqda...")
    reply = await ask_gemini(user_id, message, FALLBACK_MODEL)
    if reply:
        return reply

    # Ikkalasi ham ishlamasa
    return "Hozir biroz band bo'lib qoldim... 🙈 Bir daqiqadan keyin yozib ko'r?"


# ─── HANDLERLAR ───────────────────────────────────────────────
@dp.message(Command("start"))
async def start_handler(message: Message):
    name = message.from_user.first_name or "do'stim"
    user_histories[message.from_user.id] = []  # yangi suhbat
    await message.answer(
        f"Salom, {name}! 💕\n"
        f"Men Nilufar — sening do'sting va yordamchingman 😊\n"
        f"Gaplashamizmi? ✨"
    )

@dp.message(Command("reset"))
async def reset_handler(message: Message):
    user_histories[message.from_user.id] = []
    await message.answer("Suhbat tozalandi! Qaytadan boshlaymizmi? 🌸")

@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "📋 Buyruqlar:\n"
        "/start — boshlash\n"
        "/reset — suhbatni tozalash\n"
        "/help — yordam\n\n"
        "Istalgan narsani yoz, javob beraman! 💕"
    )

@dp.message()
async def message_handler(message: Message):
    # Matn bo'lmasa
    if not message.text:
        await message.answer("Matn yoz, men o'qiyman 😊")
        return

    # Juda qisqa xabarlar (1-2 harf)
    if len(message.text.strip()) < 2:
        await message.answer("Biroz ko'proq yoz 😊")
        return

    user_id = message.from_user.id
    await bot.send_chat_action(message.chat.id, "typing")

    reply = await get_ai_response(user_id, message.text)
    await message.answer(reply)


# ─── ISHGA TUSHIRISH ───────────────────────────────────────────
async def main():
    logger.info("Nilufar bot ishga tushdi! 🌸")
    await dp.start_polling(bot, allowed_updates=["message"])

if __name__ == "__main__":
    asyncio.run(main())
