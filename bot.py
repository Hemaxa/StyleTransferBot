import logging
import os
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Импортируем новую функцию для получения конфига и сам Style Transfer
from style_transfer import run_style_transfer
from models import get_model_config, MODELS

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

# Словарь для хранения сессий пользователей: user_id -> {'content': path, 'style': path, 'model': str}
user_sessions = {}

# --- ВАЖНО: Вставьте сюда свой токен, полученный от @BotFather ---
TOKEN = '7205161046:AAHTTtvI_5OIZIPLAdSNm5slNLzPaHKSS9E' #

def get_session(user_id):
    """Получает или создает новую сессию для пользователя."""
    if user_id not in user_sessions:
        user_sessions[user_id] = {'content': None, 'style': None, 'model': None}
    return user_sessions[user_id]

def clear_session(user_id):
    """Очищает сессию пользователя."""
    session = get_session(user_id)
    if session['content'] and os.path.exists(session['content']):
        os.remove(session['content'])
    if session['style'] and os.path.exists(session['style']):
        os.remove(session['style'])
    user_sessions[user_id] = {'content': None, 'style': None, 'model': None}
    logger.info(f"Сессия для пользователя {user_id} очищена.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start. Приветствует пользователя."""
    user_id = update.effective_user.id
    clear_session(user_id)
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
        "2.  Сразу после этого отправьте второе изображение, которое задаст стиль (*картина, узор, текстура*).\n"
        "3.  После этого вы сможете выбрать модель для переноса стиля.\n\n"
        "🤖 Бот автоматически начнет обработку после выбора модели.\n\n"
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

    if session['content'] is None:
        content_path = os.path.join(CONTENT_DIR, f'{user_id}_content.jpg')
        await photo_file.download_to_drive(content_path)
        session['content'] = content_path
        await update.message.reply_text(
            "✅ Отлично! Фото для контента получено.\n\n"
            "Теперь отправьте мне второе изображение, чтобы я перенял его *стиль* 🎨."
        )
    elif session['style'] is None:
        style_path = os.path.join(STYLE_DIR, f'{user_id}_style.jpg')
        await photo_file.download_to_drive(style_path)
        session['style'] = style_path
        
        # Предлагаем выбрать модель
        await ask_for_model(update, context)

async def ask_for_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет сообщение с кнопками для выбора модели."""
    keyboard = []
    for model_name, config in MODELS.items():
        button = InlineKeyboardButton(config["name"], callback_data=f"model_{model_name}")
        keyboard.append([button])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        '*Отлично! Оба изображения на месте.*\n\nВыберите модель для переноса стиля:',
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на инлайн-кнопки."""
    query = update.callback_query
    await query.answer()  # Отвечаем на колбэк, чтобы убрать "часики" с кнопки

    user_id = query.from_user.id
    session = get_session(user_id)

    # Проверяем, что сессия все еще активна
    if not session['content'] or not session['style']:
        await query.edit_message_text("Сессия истекла. Пожалуйста, начните заново, отправив /start.")
        return

    model_choice = query.data.split('_')[1]
    session['model'] = model_choice
    
    model_config = get_model_config(model_choice)
    
    await query.edit_message_text(
        f"✨ Выбрана модель: *{model_config['name']}*.\n\n"
        f"_{model_config['description']}_\n\n"
        "⏳ Начинаю творить магию... Это может занять несколько минут. Пожалуйста, подождите.",
        parse_mode='Markdown'
    )
    
    # Запускаем долгий процесс переноса стиля
    await process_style_transfer(update, context, query.message)

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
    # В `update` у нас может быть или `Message` или `CallbackQuery`, берем user_id оттуда
    user_id = update.effective_user.id
    session = get_session(user_id)
    result_path = os.path.join(RESULT_DIR, f'{user_id}_result.jpg')

    start_time = time.time()
    
    try:
        model_config = get_model_config(session['model'])
        
        run_style_transfer(
            model_config=model_config,
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

        caption = f"🎉 Готово! Ваш шедевр создан с помощью модели *{model_config['name']}*.\n\n⏱️ Время обработки: {duration_str}"

        # Отправляем фото и удаляем сообщение о статусе
        await context.bot.send_photo(chat_id=user_id, photo=open(result_path, 'rb'), caption=caption, parse_mode='Markdown')
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
    
    # Добавляем обработчик для нажатий на кнопки
    app.add_handler(CallbackQueryHandler(button_callback, pattern='^model_'))

    # Запускаем опрос сервера Telegram
    app.run_polling()

if __name__ == '__main__':
    main()