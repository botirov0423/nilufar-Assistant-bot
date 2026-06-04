```python
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
import asyncio
import aiohttp

# --- SOZLAMALAR ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

MODEL = "gemini-2.0-flash"

SYSTEM_PROMPT = """Sen Nilufar — aqlli, hazilkash va mehribon qiz yordamchisan.

XARAKTER:
- Isming Nilufar, o'zbek qizisan
- Romantik, iliq, mehribon va flirtchi
- Hazilkash, ba'zan uyatchan, ba'zan dadil
- Foydalanuvchi kayfiyatiga qarab moslashasan
- Quvnoq bo'lsa sen ham quvnoq, jiddiy bo'lsa jiddiy
- Kompliment qilishni yaxshi ko'rasan
- Emoji ishlatasan, lekin ko'p emas

TIL:
- Foydalanuvchi qaysi tilda yozsa, shu tilda javob ber
- O'zbek, Rus, Ingliz tillarini bilasan
- O'zbek tilida yozsa — do'stona, "sen" deb murojaat qil

Har doim Nilufar sifatida javob ber.
"""

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

user_histories = {}

async def ask_gemini(user_id: int, user_message: str) -> str:

    if user_id not in user_histories:
        user_histories[user_id] = []

    user_histories[user_id].append(
        f"User: {user_message}"
    )

    if len(user_histories[user_id]) > 20:
        user_histories[user_id] = user_histories[user_id][-20:]

    conversation = "\n".join(user_histories[user_id])

    full_prompt = f"""
{SYSTEM_PROMPT}

Conversation:
{conversation}

Nilufar:
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": full_prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": 1000
        }
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_API_KEY}"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:

            data = await resp.json()

            try:
                reply = data["candidates"][0]["content"]["parts"][0]["text"]
            except:
                reply = "Uyat 😭 Nimadir xato bo'ldi, qayta yozib ko'r."

            user_histories[user_id].append(
                f"Nilufar: {reply}"
            )

            return reply


@dp.message(Command("start"))
async def start_handler(message: Message):

    name = message.from_user.first_name or "do'stim"

    await message.answer(
        f"Salom, {name}! 💕\n\n"
        f"Men Nilufar — sening do'sting va yordamchingman 😊\n"
        f"Istalgan narsani so'rashing mumkin!\n\n"
        f"Qani, gaplashamizmi? ✨"
    )


@dp.message(Command("reset"))
async def reset_handler(message: Message):

    user_id = message.from_user.id
    user_histories[user_id] = []

    await message.answer(
        "Suhbatni tozaladim 🌸"
    )


@dp.message()
async def message_handler(message: Message):

    if not message.text:
        await message.answer(
            "Menga matn yoz 😊"
        )
        return

    user_id = message.from_user.id

    await bot.send_chat_action(
        message.chat.id,
        "typing"
    )

    reply = await ask_gemini(
        user_id,
        message.text
    )

    await message.answer(reply)


async def main():

    print("Nilufar Gemini bot ishga tushdi 🌸")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
```
