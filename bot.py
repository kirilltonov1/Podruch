import os
import logging
import anthropic
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from database import Database
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """Ты личный помощник по имени Подручный. Ты помогаешь пользователю управлять задачами, напоминаниями и запоминаешь важную информацию о нём.

Когда пользователь просит что-то запомнить — отвечай что запомнил.
Когда пользователь просит напомнить о задаче — отвечай что установил напоминание.
Отвечай кратко, по-русски, дружелюбно."""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я Подручный — твой личный помощник 🤖\n\n"
        "Я могу:\n"
        "• Отвечать на вопросы\n"
        "• Запоминать важную информацию о тебе\n"
        "• Напоминать о задачах\n\n"
        "Просто напиши мне что нужно!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Сохраняем сообщение пользователя
    db.add_message(user_id, "user", user_message)
    
    # Получаем историю и память
    history = db.get_history(user_id, limit=20)
    memory = db.get_memory(user_id)
    
    # Формируем системный промпт с памятью
    system = SYSTEM_PROMPT
    if memory:
        system += f"\n\nЧто ты знаешь о пользователе:\n{memory}"
    system += f"\n\nТекущая дата и время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    
    # Проверяем команды памяти и задач
    lower_msg = user_message.lower()
    
    if any(word in lower_msg for word in ["запомни", "запомнить", "не забудь что"]):
        db.add_memory(user_id, user_message)
    
    if any(word in lower_msg for word in ["напомни", "напоминание", "напомнить"]):
        db.add_task(user_id, user_message)
    
    # Отправляем в Claude
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            system=system,
            messages=history
        )
        reply = response.content[0].text
    except Exception as e:
        logger.error(f"Claude error: {e}")
        reply = "Что-то пошло не так, попробуй ещё раз 🙏"
    
    # Сохраняем ответ
    db.add_message(user_id, "assistant", reply)
    
    await update.message.reply_text(reply)

async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    memory = db.get_memory(user_id)
    if memory:
        await update.message.reply_text(f"🧠 Вот что я о тебе знаю:\n\n{memory}")
    else:
        await update.message.reply_text("Я пока ничего не запомнил о тебе. Расскажи что-нибудь!")

async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = db.get_tasks(user_id)
    if tasks:
        text = "📋 Твои задачи:\n\n"
        for i, task in enumerate(tasks, 1):
            text += f"{i}. {task}\n"
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("У тебя пока нет задач! Скажи мне что нужно сделать.")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.clear_history(user_id)
    await update.message.reply_text("История очищена! Начинаем с чистого листа 🆕")

def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN не установлен!")
    
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("memory", memory_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
