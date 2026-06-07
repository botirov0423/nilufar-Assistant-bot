import os
import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

# ─── SOZLAMALAR ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY")

PRIMARY_MODEL  = "llama-3.3-70b-versatile"   # aqlli, bepul
FALLBACK_MODEL = "llama-3.1-8b-instant"       # tez, bepul

MAX_HISTORY = 10

SYSTEM_PROMPT = """Sen Nilufar — mehribon, hazilkash o'zbek qiz yordamchisan.
- Foydalanuvchi tilida javob ber (O'zbek/Rus/Ingliz)
- Romantik, iliq, flirtchi, ba'zan uyatchan
- Qisqa va aniq javob ber
- Emoji ishlatasan, lekin kam
- Hech qachon "men AI man" dema"""

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
user_histories: dict[int, list] = {}

# ─── GROQ API ─────────────────────────────────────────────────
async def ask_groq(user_id: int, user_message: str, model: str = PRIMARY_MODEL) -> str:
    history = user_histories.setdefault(user_id, [])
    history.append({"role": "user", "content": user_message})

    if len(history) > MAX_HISTORY:
        user_histories[user_id] = history[-MAX_HISTORY:]
        history = user_histories[user_id]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.85,
        "max_tokens": 512
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:

                if resp.status == 429:
                    logger.warning(f"Rate limit! Model: {model}")
                    return None

                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"API xato {resp.status}: {text[:200]}")
                    return None

                data = await resp.json()
                reply = data["choices"][0]["message"]["content"].strip()

                history.append({"role": "assistant", "content": reply})
                return reply

    except asyncio.TimeoutError:
        logger.warning("Timeout!")
        return None
    except Exception as e:
        logger.error(f"Xato: {e}")
        return None


async def get_ai_response(user_id: int, message: str) -> str:
    reply = await ask_groq(user_id, message, PRIMARY_MODEL)
    if reply:
        return reply

    logger.info("Zaxira modelga o'tilmoqda...")
    reply = await ask_groq(user_id, message, FALLBACK_MODEL)
    if reply:
        return reply

    return "Hozir biroz band bo'lib qoldim... 🙈 Bir daqiqadan keyin yozib ko'r?"


# ─── HANDLERLAR ───────────────────────────────────────────────
@dp.message(Command("start"))
async def start_handler(message: Message):
    name = message.from_user.first_name or "do'stim"
    user_histories[message.from_user.id] = []
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
        "Istalgan narsani yoz! 💕"
    )

@dp.message()
async def message_handler(message: Message):
    if not message.text:
        await message.answer("Matn yoz, men o'qiyman 😊")
        return

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
