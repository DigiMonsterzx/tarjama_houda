import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, ContextTypes
from googletrans import Translator
import cloudinary.uploader
from supabase import create_client, Client

# Set up environment variables for Cloudinary and Supabase
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(supabase_url, supabase_key)

# Initialize the translator
translator = Translator()

# Step 3: Define Bot Functions
def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update.message.reply_text("Welcome! Please upload a Word file to start the translation process.")

def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ask user to choose the original language
    keyboard = [
        [InlineKeyboardButton("English (EN)", callback_data='en')],
        [InlineKeyboardButton("French (FR)", callback_data='fr')],
        [InlineKeyboardButton("Spanish (ES)", callback_data='es')],
        [InlineKeyboardButton("Arabic (AR)", callback_data='ar')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.user_data['file_id'] = update.message.document.file_id
    update.message.reply_text('Please choose the original language:', reply_markup=reply_markup)

def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['original_language'] = query.data
    query.answer()

    # Ask user to choose the target language
    keyboard = [
        [InlineKeyboardButton("English (EN)", callback_data='en')],
        [InlineKeyboardButton("French (FR)", callback_data='fr')],
        [InlineKeyboardButton("Spanish (ES)", callback_data='es')],
        [InlineKeyboardButton("Arabic (AR)", callback_data='ar')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text="Please choose the target language:", reply_markup=reply_markup)

def handle_translation_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['convert_to'] = query.data
    query.answer()

    # Download the file from Telegram
    file_id = context.user_data['file_id']
    file = context.bot.get_file(file_id)
    file_path = file.download()

    # Upload the file to Cloudinary
    response = cloudinary.uploader.upload(file_path, resource_type="auto")
    file_url = response['url']

    # Store the data in Supabase
    supabase.table('translatix').insert({
        'id_telegram': query.message.chat_id,
        'file_url': file_url,
        'original_language': context.user_data['original_language'],
        'convert_to': context.user_data['convert_to'],
        'status': 'Queued'
    }).execute()

    query.edit_message_text(text=f"Your file has been uploaded and queued for translation. File URL: {file_url}")

# Step 4: Main Function to Run the Bot
def main():
    updater = Updater(os.getenv('TELEGRAM_TOKEN'), use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.document.mime_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document"), handle_document))
    dp.add_handler(CallbackQueryHandler(handle_language_selection, pattern='^(en|fr|es|ar)$'))
    dp.add_handler(CallbackQueryHandler(handle_translation_selection, pattern='^(en|fr|es|ar)$'))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
