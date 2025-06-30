import logging
import os
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Ваш файл со всей логикой переноса стиля. Убедитесь, что он лежит рядом.
from style_transfer import run_style_transfer, cnn, cnn_normalization_mean, cnn_normalization_std

# Включаем логирование для отладки
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Папки для сохранения изображений
CONTENT_DIR = 'images/content'
STYLE_DIR = 'images/style'
RESULT_DIR = 'images/result'

# Создаем папки, если их не существует
os.makedirs(CONTENT_DIR, exist_ok=True)
os.makedirs(STYLE_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# Словарь для хранения сессий пользователей: user_id -> {'content': path, 'style': path}
user_sessions = {}

# --- ВАЖНО: Вставьте сюда свой токен, полученный от @BotFather ---
TOKEN = '7205161046:AAHTTtvI_5OIZIPLAdSNm5slNLzPaHKSS9E' #

def get_session(user_id):
    """Получает или создает новую сессию для пользователя."""
    if user_id not in user_sessions:
        user_sessions[user_id] = {'content': None, 'style': None}
    return user_sessions[user_id]

def clear_session(user_id):
    """Очищает сессию пользователя."""
    session = get_session(user_id)
    if session['content'] and os.path.exists(session['content']):
        os.remove(session['content'])
    if session['style'] and os.path.exists(session['style']):
        os.remove(session['style'])
    user_sessions[user_id] = {'content': None, 'style': None}
    logger.info(f"Сессия для пользователя {user_id} очищена.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start. Приветствует пользователя."""
    user_id = update.effective_user.id
    clear_session(user_id)  # Очищаем старую сессию на случай, если она осталась
    await update.message.reply_text(
        "👋 *Привет! Я — Style Transfer Бот* 🎨\n\n"
        "Я могу превратить ваше фото в произведение искусства, используя стиль другой картины.\n\n"
        "1️⃣ Сначала отправьте мне фото, которое хотите изменить (*контент*).\n"
        "2️⃣ Затем отправьте фото, стиль которого хотите применить (*стиль*).\n\n"
        "Начнем! Жду первое изображение.",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help. Показывает инструкцию."""
    await update.message.reply_text(
        "ℹ️ *Как мной пользоваться:*\n\n"
        "1.  Отправьте мне изображение, которое будет основой (*фотография, пейзаж и т.д.*).\n"
        "2.  Сразу после этого отправьте второе изображение, которое задаст стиль (*картина, узор, текстура*).\n\n"
        "🤖 Бот автоматически начнет обработку после получения второго фото.\n\n"
        "Если вы передумали или что-то пошло не так, используйте команду /clear, чтобы начать заново.",
        parse_mode='Markdown'
    )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /clear. Сбрасывает текущую сессию."""
    user_id = update.effective_user.id
    clear_session(user_id)
    await update.message.reply_text(
        "🗑️ Все в порядке! Я удалил загруженные фото. Можете начать сначала."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает загруженные пользователем фотографии."""
    user_id = update.effective_user.id
    session = get_session(user_id)
    
    photo_file = await update.message.photo[-1].get_file()

    # Если первое изображение (контент) еще не загружено
    if session['content'] is None:
        content_path = os.path.join(CONTENT_DIR, f'{user_id}_content.jpg')
        await photo_file.download_to_drive(content_path)
        session['content'] = content_path
        await update.message.reply_text(
            "✅ Отлично! Фото для контента получено.\n\n"
            "Теперь отправьте мне второе изображение, чтобы я перенял его *стиль* 🎨."
        )
    # Если второе изображение (стиль) еще не загружено
    elif session['style'] is None:
        style_path = os.path.join(STYLE_DIR, f'{user_id}_style.jpg')
        await photo_file.download_to_drive(style_path)
        session['style'] = style_path
        
        message = await update.message.reply_text(
            "✨ Прекрасно! Оба изображения на месте.\n\n"
            "⏳ Начинаю творить магию... Это может занять несколько минут. Пожалуйста, подождите."
        )
        # Запускаем долгий процесс переноса стиля
        await process_style_transfer(update, context, message)

def format_duration(seconds):
    """Форматирует секунды в минуты и секунды."""
    if seconds < 60:
        return f"{int(seconds)} сек."
    else:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins} мин. {secs} сек."

async def process_style_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE, status_message):
    """Запускает перенос стиля, замеряет время и отправляет результат."""
    user_id = update.effective_user.id
    session = get_session(user_id)
    result_path = os.path.join(RESULT_DIR, f'{user_id}_result.jpg')

    start_time = time.time()
    
    try:
        # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
        # Мы напрямую вызываем вашу синхронную функцию, как и должно быть.
        # Это самый простой и надежный способ в данном случае.
        run_style_transfer(
            cnn=cnn,
            normalization_mean=cnn_normalization_mean,
            normalization_std=cnn_normalization_std,
            content_img_path=session['content'],
            style_img_path=session['style'],
            output_img_path=result_path,
            num_steps=800,
            style_weight=50000,
            content_weight=1
        )
        
        end_time = time.time()
        duration = end_time - start_time
        duration_str = format_duration(duration)

        caption = f"🎉 Готово! Ваш шедевр создан.\n\n⏱️ Время обработки: {duration_str}"

        # Отправляем фото и удаляем сообщение о статусе
        await context.bot.send_photo(chat_id=user_id, photo=open(result_path, 'rb'), caption=caption)
        await status_message.delete()

    except Exception as e:
        logger.error(f"Ошибка при переноса стиля для user_id {user_id}: {e}")
        await status_message.edit_text(
            "😥 Ой, что-то пошло не так во время обработки.\n\n"
            "Пожалуйста, попробуйте еще раз с другими изображениями или используйте команду /clear для сброса."
        )
    finally:
        # Очищаем сессию пользователя после завершения
        clear_session(user_id)


def main():
    """Запускает бота."""
    logger.info("Бот запускается...")
    
    app = ApplicationBuilder().token(TOKEN).build()

    # Добавляем обработчики команд
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('clear', clear_command))

    # Добавляем обработчик для всех входящих фотографий
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Запускаем опрос сервера Telegram
    app.run_polling()

if __name__ == '__main__':
    main()