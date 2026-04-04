import os
import re
import asyncio
import pytz
from datetime import datetime
from telethon import TelegramClient, events
from groq import AsyncGroq
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
GROQ_KEY = os.getenv('GROQ_KEY')
TARGET_CHANNEL_ID = int(os.getenv('TARGET_CHANNEL_ID'))
TIMEZONE = pytz.timezone('Europe/Belgrade')

client = TelegramClient('moderator_session', API_ID, API_HASH)
groq_client = AsyncGroq(api_key=GROQ_KEY)

def get_now():
    return datetime.now(TIMEZONE).strftime('%H:%M:%S')

class AIModerator:
    def __init__(self):
        self.safe_links = ["t.me/spb_live_channel", "piter.ru"]
        self.system_prompt = (
            "Ты — интеллигентный модератор сообщества о Петербурге. "
            "Удаляй (SPAM): жесткий мат, рекламу наркотиков, эскорт. "
            "Пропускай (OK): сленг, обсуждение города. "
            "Отвечай строго одним словом: SPAM или OK."
        )

    async def is_spam(self, text):
        link_pattern = r"(https?://\S+|t\.me/\S+|@\w+)"
        found_links = re.findall(link_pattern, text)
        for link in found_links:
            if not any(safe in link for safe in self.safe_links):
                return True, "Forbidden Link"

        try:
            chat_completion = await groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0,
                max_tokens=5
            )
            result = chat_completion.choices[0].message.content.strip().upper()
            return "SPAM" in result, "AI Verdict"
        except Exception as e:
            print(f"⚠️ Ошибка нейросети: {e}")
            return False, "Error"

moderator = AIModerator()

@client.on(events.NewMessage(chats=TARGET_CHANNEL_ID))
async def handler(event):
    if not event.text:
        return

    # --- УЛУЧШЕННАЯ ПРОВЕРКА НА АДМИНА ---
    try:
        # 1. Если сообщение отправлено от имени самого канала — это точно админ
        if event.sender_id == event.chat_id:
            return

        # 2. Проверяем права через get_permissions
        # Для каналов это работает стабильнее, чем GetParticipantRequest
        permissions = await client.get_permissions(event.chat_id, event.sender_id)
        
        if permissions.is_admin or permissions.is_creator:
            print(f"[{get_now()}] ℹ️ Админ {event.sender_id} пропущен.")
            return
            
    except Exception as e:
        # Если пользователя нет в участниках (например, он зашел по ссылке и сразу написал)
        # или возникла ошибка GetParticipant, мы просто логируем это и идем дальше к проверке на спам
        print(f"⚠️ Инфо: Пользователь {event.sender_id} не в списке участников или скрыт. Проверяем как обычного юзера.")
    # ------------------------------------

    # Если это не админ, проверяем на спам
    spam_detected, reason = await moderator.is_spam(event.text)
    
    if spam_detected:
        print(f"[{get_now()}] 🛡️ Удалено! Причина: {reason}")
        try:
            await event.delete()
        except Exception as e:
            print(f"❌ Ошибка удаления: {e}")

async def main():
    await client.start(bot_token=BOT_TOKEN)
    print(f"✅ Модератор запущен в {get_now()}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())