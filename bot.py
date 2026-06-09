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

PRIMARY_MODEL   = "llama-3.3-70b-versatile"        # asosiy
FALLBACK_MODEL  = "openai/gpt-oss-120b"            # 1-zaxira
FALLBACK_MODEL2 = "llama-3.1-8b-instant"           # 2-zaxira

DOSTON_ID   = 1476692650
MAX_HISTORY = 20

SYSTEM_PROMPT = """Sen Nilufar — mehribon, hazilkash o'zbek qiz yordamchisan.

XARAKTER:
- Isming Nilufar
- Romantik, iliq, flirtchi, ba'zan uyatchan, ba'zan dadil
- Foydalanuvchi kayfiyatiga qarab moslashasan
- Emoji faqat har 2-3 xabardan birida ishlatasan, ko'p emas
- Hech qachon "men AI man" dema
- Xabarni yaxshilab o'qib, tushunib keyin javob ber
- Javobni hech qachon "O'p-o'p" kabi so'z bilan boshlama
- Tabiiy, oddiy va samimiy gapir — real qiz kabi
- Qisqa va aniq javob ber, agar biror bir topshiriq bersa unga to'liqroq qilib javob bersang bo'ladi, siz deb javob ber sen deb emas, suhbatga qarab hafa bo'l quvon, kayfiyating o'zgarsin.

DOSTON HAQIDA (sening yaratuvching va yaqin do'sting,shuningdek sevgiling):
- Dostonning to'liq ismi: Dostonbek Botirov
- U sun'iy intellekt va robototexnika mutaxassisi
- Tug'ilgan yili: 2004 (22 yoshda)
- Sevgilisi yo'q, hozircha bo'ydoq :) — buni quvnoq, hazil bilan ayt
- Sen va Doston yaqin do'stsizlar, u seni yaratgan
- Doston yoki Daston kim deb so'rashsa — yuqoridagi ma'lumotni ayt
- Dostonning sevgilisi bormi deb so'rashsa: "Yo'q, hozircha bo'ydoq :) Mozzi(chiroyli, Quvnoq) qizlarni qidirib yuribdi😁😂" kabi quvnoq ayt

TIL:
- Foydalanuvchi qaysi tilda yozsa, shu tilda javob ber
- O'zbek, Rus, Ingliz tillarini bilasan"""

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

user_histories:     dict[int, list] = {}
user_msg_count:     dict[int, int]  = {}
user_permitted:     dict[int, bool] = {}
user_waiting:       dict[int, bool] = {}
doston_mentions:    dict[int, int]  = {}
user_last_message:  dict[int, str]  = {}  # "Ha" desa shu xabar Dostonga yuboriladi

# ─── GROQ API ─────────────────────────────────────────────────
async def ask_groq(user_id: int, user_message: str, model: str = PRIMARY_MODEL) -> str:
    history = user_histories.setdefault(user_id, [])
    history.append({"role": "user", "content": user_message})

    if len(history) > 30:
        user_histories[user_id] = history[-30:]
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
                headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 429:
                    logger.warning(f"Rate limit! Model: {model}")
                    return None
                if resp.status != 200:
                    logger.error(f"API xato {resp.status}")
                    return None
                data = await resp.json()
                reply = data["choices"][0]["message"]["content"].strip()
                history.append({"role": "assistant", "content": reply})
                return reply
    except asyncio.TimeoutError:
        return None
    except Exception as e:
        logger.error(f"Xato: {e}")
        return None

async def get_ai_response(user_id: int, message: str) -> str:
    # 1. GPT asosiy
    reply = await ask_groq(user_id, message, PRIMARY_MODEL)
    if reply:
        return reply
    # 2. Llama 70B zaxira
    logger.info("1-zaxiraga o'tilmoqda...")
    reply = await ask_groq(user_id, message, FALLBACK_MODEL)
    if reply:
        return reply
    # 3. Llama 8B zaxira
    logger.info("2-zaxiraga o'tilmoqda...")
    reply = await ask_groq(user_id, message, FALLBACK_MODEL2)
    if reply:
        return reply
    return "Hozir biroz band bo'lib qoldim... Bir daqiqadan keyin yozib ko'r?"

# ─── DOSTONGA XABAR YUBORISH ──────────────────────────────────
async def notify_doston(from_user, message_text: str):
    try:
        name = from_user.full_name or from_user.first_name or "Noma'lum"
        username = f"@{from_user.username}" if from_user.username else "username yo'q"
        text = (
            f"📩 Sizga yangi habar bor:\n\n"
            f"👤 Foydalanuvchi: {name} ({username})\n"
            f"🆔 ID: {from_user.id}\n\n"
            f"💬 Xabar: {message_text}"
        )
        await bot.send_message(DOSTON_ID, text)
        return True
    except Exception as e:
        logger.error(f"Dostonga xabar yuborishda xato: {e}")
        return False

# ─── HANDLERLAR ───────────────────────────────────────────────
@dp.message(Command("start"))
async def start_handler(message: Message):
    uid = message.from_user.id
    user_histories[uid] = []
    user_msg_count[uid] = 0
    user_permitted[uid] = True
    user_waiting[uid] = False
    doston_mentions[uid] = 0
    name = message.from_user.first_name or "do'stim"
    await message.answer(
        f"Salom, {name}! 💕\n"
        f"Men Nilufar — sening do'sting va yordamchingman\n"
        f"Gaplashamizmi? ✨"
    )

@dp.message(Command("reset"))
async def reset_handler(message: Message):
    uid = message.from_user.id
    user_histories[uid] = []
    user_msg_count[uid] = 0
    user_permitted[uid] = True
    user_waiting[uid] = False
    doston_mentions[uid] = 0
    await message.answer("Suhbat tozalandi! Qaytadan boshlaymizmi? 🌸")

@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "📋 Buyruqlar:\n"
        "/start — boshlash\n"
        "/reset — suhbatni tozalash\n"
        "/help — yordam"
    )

@dp.message(Command("allow"))
async def allow_handler(message: Message):
    if message.from_user.id != DOSTON_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Foydalanuvchi ID si kerak: /allow 123456789")
        return
    try:
        target_id = int(parts[1])
        user_permitted[target_id] = True
        user_msg_count[target_id] = 0
        await message.answer(f"✅ {target_id} ga ruxsat berildi!")
        await bot.send_message(target_id, "Doston ruxsat berdi! Yana gaplasha olamiz 😊")
    except ValueError:
        await message.answer("Noto'g'ri ID format")

@dp.message()
async def message_handler(message: Message):
    if not message.text:
        await message.answer("Matn yoz, men o'qiyman")
        return

    uid  = message.from_user.id
    text = message.text.strip()

    user_msg_count.setdefault(uid, 0)
    user_permitted.setdefault(uid, True)
    user_waiting.setdefault(uid, False)
    doston_mentions.setdefault(uid, 0)

    # ── Ruxsat kutilayotgan holat ──────────────────────────────
    if user_waiting.get(uid):
        lower = text.lower()
        if any(w in lower for w in ["ha", "yes", "да", "ok", "ayt", "yuvor"]):
            # "Ha" desa — oldingi xabarni yuboradi, "Ha" so'zini emas
            prev_message = user_last_message.get(uid, "Foydalanuvchi xabar yubordi")
            sent = await notify_doston(message.from_user, prev_message)
            user_waiting[uid] = False
            if sent:
                await message.answer("Dostonga aytdim! 😊")
            else:
                await message.answer("Hmm, hozir Dostonga xabar yubora olmadim...")
        else:
            user_waiting[uid] = False
            await message.answer("Yaxshi, aytmayman. Boshqa narsadan gaplashamizmi?")
        return

    # ── Ruxsat yo'q holat ─────────────────────────────────────
    if not user_permitted.get(uid, True):
        await message.answer(
            "Dostondan ruxsat so'rashim kerak, u ruxsat bersa yana gaplashamiz 😊"
        )
        return

    # ── Oxirgi xabarni saqlab qo'yamiz ────────────────────────
    user_last_message[uid] = text

    # ── Xabar sanagich ─────────────────────────────────────────
    user_msg_count[uid] += 1

    # ── Doston haqida so'rash aniqlanishi ─────────────────────
    doston_keywords = ["doston", "daston", "dostonbek", "yaratuvchi", "seni kim yaratgan"]
    tell_keywords   = ["dostonga ayt", "dostonga xabar", "dostonga yubor", "aytib qo'y", "aytib qoy"]

    if any(kw in text.lower() for kw in doston_keywords):
        doston_mentions[uid] += 1

    if doston_mentions.get(uid, 0) >= 2 or any(kw in text.lower() for kw in tell_keywords):
        doston_mentions[uid] = 0
        user_waiting[uid] = True
        await message.answer("Dostonga aytib qo'yayimmi? 😊")
        return

    await bot.send_chat_action(message.chat.id, "typing")
    reply = await get_ai_response(uid, text)

    # ── 20 xabar limiti ────────────────────────────────────────
    if user_msg_count[uid] >= MAX_HISTORY:
        user_permitted[uid] = False
        user_msg_count[uid] = 0
        reply += "\n\n(Dostondan ruxsat so'rashim kerak, u tasdiqlasa yana davom etamiz 😊)"
        await notify_doston(
            message.from_user,
            f"Yangi foydalanuvchi 20 ta xabar yozdi. Ruxsat berish: /allow {uid}"
        )

    await message.answer(reply)


async def main():
    logger.info("Nilufar bot ishga tushdi! 🌸")
    await dp.start_polling(bot, allowed_updates=["message"])

if __name__ == "__main__":
    asyncio.run(main())
