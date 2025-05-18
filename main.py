import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import requests
from dotenv import load_dotenv

# === Настройка логирования ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)
logger = logging.getLogger(__name__)

# === Загрузка переменных окружения ===
load_dotenv()

# === Настройки из .env ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
HF_API_KEY = os.getenv("HF_API_KEY")

# === URL модели ===
API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3 "
headers = {"Authorization": f"Bearer {HF_API_KEY}"}

# === Контекст диалога ===
MAX_HISTORY_LENGTH = 10  # Максимум записей в истории

# === Хранилище для истории ===
user_histories = {}  # {chat_id: ["User: Привет", "Bot: Здравствуйте"]}

# === Формирование промта с историей ===
def build_prompt(chat_id, new_message):
    history = user_histories.get(chat_id, [])
    history.append(f"User: {new_message}")
    prompt = "\n".join(history[-MAX_HISTORY_LENGTH:])  # Оставляем последние N сообщений
    return prompt

# === Обновление истории ===
def update_history(chat_id, bot_response):
    history = user_histories.get(chat_id, [])
    history.append(f"Bot: {bot_response}")
    user_histories[chat_id] = history[-MAX_HISTORY_LENGTH:]

# === Вызов модели ===
def query(prompt: str):
    try:
        logger.info(f"Запрос к Mistral: {prompt}")
        response = requests.post(API_URL, headers=headers, json={
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 512,
                "temperature": 0.7,
                "wait_for_model": True
            }
        })

        # Логируем сырой ответ
        logger.debug(f"[DEBUG] Raw ответ от сервера: {response.text[:500]}...")

        if "application/json" in response.headers.get("Content-Type", ""):
            return response.json()
        else:
            logger.error(f"Ошибка: Получен не JSON. Ответ сервера: '{response.text[:500]}'")
            return {"error": "Неожиданный формат ответа от сервера"}
            
    except Exception as e:
        logger.error(f"Ошибка при обращении к модели: {e}")
        return {"error": str(e)}

# === Обработка ответа ===
async def get_ai_response(chat_id, prompt: str) -> str:
    output = query(prompt)

    if "error" in output:
        logger.warning(f"Ошибка генерации: {output['error']}")
        return f"Ошибка: {output['error']}"

    if isinstance(output, list) and "generated_text" in output[0]:
        text = output[0]["generated_text"]
    elif "generated_text" in output:
        text = output["generated_text"]
    else:
        return "Не могу ответить."

    logger.info(f"Ответ от модели: {text}")
    update_history(chat_id, text.strip())
    return text.strip()

# === Команда /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_histories[chat_id] = []  # Начинаем новую историю
    logger.info(f"Пользователь {chat_id} начал новый диалог")
    await update.message.reply_text("Привет! Я помню предыдущие сообщения. Спрашивайте на русском.")

# === Обработка сообщений ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_text = update.message.text
    logger.info(f"Сообщение от {chat_id}: {user_text}")

    await update.message.reply_text("Подождите, я думаю...")
    prompt = build_prompt(chat_id, user_text)
    answer = await get_ai_response(chat_id, prompt)
    await update.message.reply_text(answer)

# === Точка входа ===
def main():
    logger.info("Бот запускается...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()
