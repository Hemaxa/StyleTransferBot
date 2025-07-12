import logging
import os
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Импортируем функции из наших модулей
from core.vgg_transfer import run_style_transfer
from core.gan_transfer import run_gan_transfer
from models.vgg_definitions import MODELS_VGG, get_vgg_config

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройки папок
CONTENT_DIR = 'images/content'
STYLE_DIR = 'images/style'
RESULT_DIR = 'images/result'
os.makedirs(CONTENT_DIR, exist_ok=True)
os.makedirs(STYLE_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

TOKEN = '7205161046:AAHTTtvI_5OIZIPLAdSNm5slNLzPaHKSS9E' # ВАШ ТОКЕН
user_sessions = {}

# --- Управление сессиями ---

def get_session(user_id):
    """Получает или создает новую сессию для пользователя."""
    if user_id not in user_sessions:
        user_sessions[user_id] = {'content': None, 'style': None, 'model': None}
    return user_sessions[user_id]

def clear_session_files(user_id):
    """Очищает только файлы сессии, сохраняя выбранную модель."""
    session = get_session(user_id)
    if session.get('content') and os.path.exists(session['content']):
        os.remove(session['content'])
        session['content'] = None
    if session.get('style') and os.path.exists(session['style']):
        os.remove(session['style'])
        session['style'] = None
    logger.info(f"Файлы для сессии {user_id} очищены.")

# --- Обработчики команд ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start. Приветствует и предлагает выбор модели."""
    user_id = update.effective_user.id
    get_session(user_id) # Создаем сессию, если ее нет
    clear_session_files(user_id) # Очищаем старые файлы
    await context.bot.send_message(
        chat_id=user_id,
        text=f"👋 *Привет, {update.effective_user.first_name}!* Я — бот, который превращает твои фото в произведения искусства.",
        parse_mode='Markdown'
    )
    await ask_for_model(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help. Показывает подробную инструкцию."""
    await update.message.reply_text(
        "ℹ️ *Подробная инструкция:*\n\n"
        "Я могу переносить стиль с одной картины на другую, используя нейронные сети. Вот как это работает:\n\n"
        "1️⃣ *Выберите модель*:\n"
        "   - `🎨 Стиль Моне (GAN)`: Очень быстрая модель. Превращает любое ваше фото в картину в стиле Клода Моне. Требует *всего одно фото*.\n"
        "   - `🖼️ VGG-модели`: Классический метод. Требует *два фото*: одно для контента (что будет на картине) и одно для стиля (как будет нарисовано). Работает медленнее, но позволяет использовать любой стиль.\n\n"
        "2️⃣ *Отправьте фото*:\n"
        "   - Следуйте инструкциям после выбора модели.\n\n"
        "3️⃣ *Получите результат*:\n"
        "   - После обработки я пришлю вам готовую картину и предложу стилизовать еще одно фото или сменить модель.\n\n"
        "*Доступные команды:*\n"
        "/start - Начать работу или сбросить сессию.\n"
        "/help - Показать эту справку.",
        parse_mode='Markdown'
    )

# --- Обработчики сообщений и кнопок ---

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает загруженные пользователем фотографии."""
    user_id = update.effective_user.id
    session = get_session(user_id)
    
    if not session.get('model'):
        await update.message.reply_text("🤔 Кажется, вы еще не выбрали модель. Пожалуйста, выберите модель из списка ниже, чтобы я знал, что делать с фото.", parse_mode='Markdown')
        await ask_for_model(update, context)
        return

    photo_file = await update.message.photo[-1].get_file()
    status_message = None

    # Логика для GAN модели (требует 1 фото)
    if session['model'] == 'gan_monet':
        content_path = os.path.join(CONTENT_DIR, f'{user_id}_content.jpg')
        await photo_file.download_to_drive(content_path)
        session['content'] = content_path
        status_message = await update.message.reply_text("🎨 Применяю стиль Моне... Это будет очень быстро!")
        await process_style_transfer(update, context, status_message)
    
    # Логика для VGG моделей (требует 2 фото)
    else:
        if session['content'] is None:
            content_path = os.path.join(CONTENT_DIR, f'{user_id}_content.jpg')
            await photo_file.download_to_drive(content_path)
            session['content'] = content_path
            await update.message.reply_text("✅ Отлично! Это фото для *контента*. Теперь пришлите фото для *стиля*.", parse_mode='Markdown')
        elif session['style'] is None:
            style_path = os.path.join(STYLE_DIR, f'{user_id}_style.jpg')
            await photo_file.download_to_drive(style_path)
            session['style'] = style_path
            status_message = await update.message.reply_text("⏳ Начинаю творить магию... Это может занять несколько минут, пожалуйста, подождите.")
            await process_style_transfer(update, context, status_message)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отвечает на текстовые сообщения, направляя пользователя."""
    await update.message.reply_text(
        "Я бот для обработки изображений 🖼️\n\n"
        "Пожалуйста, отправьте мне фотографию или используйте команду /start, чтобы начать."
    )

async def ask_for_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет или редактирует сообщение, предлагая выбор модели."""
    keyboard = [
        [InlineKeyboardButton("🎨 Стиль Моне (Быстро, GAN)", callback_data="model_gan_monet")],
        [InlineKeyboardButton("🖼️ VGG-16 (Быстрый)", callback_data="model_vgg16")],
        [InlineKeyboardButton("✨ VGG-19 (Детальный)", callback_data="model_vgg19")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = '👇 Пожалуйста, выберите модель для переноса стиля:'
    
    # Если это ответ на нажатие кнопки, редактируем сообщение. Иначе - отправляем новое.
    if update.callback_query:
        await update.callback_query.message.edit_text(message_text, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=reply_markup)

async def model_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор модели."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    session = get_session(user_id)
    clear_session_files(user_id) # Очищаем старые фото при выборе новой модели
    
    model_choice = query.data.split('model_')[1]
    session['model'] = model_choice
    
    if model_choice == 'gan_monet':
        reply_text = "✨ *Стиль Моне (GAN)*\n\nОтлично! Эта модель мгновенно превратит ваше фото в шедевр импрессионизма. Просто отправьте мне одну фотографию."
    else:
        model_config = get_vgg_config(model_choice)
        reply_text = f"✨ *{model_config['name']}*\n\n{model_config['description']}\n\nТеперь, пожалуйста, отправьте фото для **контента** (что будет на картине)."
    
    await query.edit_message_text(text=reply_text, parse_mode='Markdown')

async def action_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает кнопки действий после переноса стиля."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    action = query.data.split('action_')[1]

    if action == 'try_another':
        await query.message.delete() # Удаляем сообщение с кнопками
        model_name = get_session(user_id).get('model')
        # Очищаем только файлы, чтобы бот снова ждал фото для контента (и стиля для VGG)
        clear_session_files(user_id)
        if model_name == 'gan_monet':
            await context.bot.send_message(chat_id=user_id, text="Отлично! 👍 Жду следующую фотографию для стилизации под Моне.")
        else:
            await context.bot.send_message(chat_id=user_id, text="Хорошо! 👍 Сначала отправьте фото для контента, а затем для стиля.")
    
    elif action == 'change_model':
        await ask_for_model(update, context)

# --- Основной процесс ---

async def process_style_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE, status_message=None):
    """Запускает перенос стиля, замеряет время и отправляет результат с кнопками."""
    user_id = update.effective_user.id
    session = get_session(user_id)
    result_path = os.path.join(RESULT_DIR, f'{user_id}_result_{int(time.time())}.jpg')
    model_name = session['model']

    start_time = time.time()
    try:
        # Логика переноса стиля
        if model_name == 'gan_monet':
            run_gan_transfer(content_img_path=session['content'], output_img_path=result_path)
            caption = "🎉 Готово! Ваш шедевр в стиле Моне."
        else:
            model_config = get_vgg_config(model_name)
            run_style_transfer(model_config=model_config, content_img_path=session['content'], style_img_path=session['style'], output_img_path=result_path)
            caption = f"🎉 Готово! Результат от модели *{model_config['name']}*."
        
        duration_str = f"{time.time() - start_time:.1f} сек."
        final_caption = f"{caption}\n\n⏱️ Время обработки: {duration_str}"
        
        await context.bot.send_photo(chat_id=user_id, photo=open(result_path, 'rb'), caption=final_caption, parse_mode='Markdown')
        if status_message: await status_message.delete()

        # Отправка кнопок для следующих действий
        keyboard = [
            [InlineKeyboardButton("🖼️ Стилизовать еще одно фото", callback_data="action_try_another")],
            [InlineKeyboardButton("⚙️ Сменить модель", callback_data="action_change_model")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=user_id, text="Что делаем дальше?", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка при переносе стиля для user_id {user_id}: {e}")
        error_message = "😥 Ой, что-то пошло не так. Возможно, файл изображения поврежден или имеет неподдерживаемый формат. Попробуйте еще раз с другим фото или начните заново с /start"
        if status_message: await status_message.edit_text(error_message)
        else: await context.bot.send_message(chat_id=user_id, text=error_message)
    finally:
        # Очищаем только временные файлы, модель в сессии остается
        if os.path.exists(result_path): os.remove(result_path)
        clear_session_files(user_id)

def main():
    """Запускает бота."""
    logger.info("Бот запускается...")
    app = ApplicationBuilder().token(TOKEN).build()

    # Команды
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))

    # Обработчики сообщений
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Обработчики кнопок
    app.add_handler(CallbackQueryHandler(model_button_callback, pattern='^model_'))
    app.add_handler(CallbackQueryHandler(action_button_callback, pattern='^action_'))

    app.run_polling()
    logger.info("Бот остановлен.")

if __name__ == '__main__':
    main()