import os
import cloudinary.uploader
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from supabase import create_client, Client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from googletrans import Translator
from telegram.constants import ParseMode
import uvicorn

# Initialize FastAPI
app = FastAPI()

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

# Initialize the bot application
app_bot = ApplicationBuilder().token(os.getenv('TELEGRAM_TOKEN')).build()

# Define Bot Functions
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Please upload a Word file to start the translation process.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("English (EN)", callback_data='en')],
        [InlineKeyboardButton("French (FR)", callback_data='fr')],
        [InlineKeyboardButton("Spanish (ES)", callback_data='es')],
        [InlineKeyboardButton("Arabic (AR)", callback_data='ar')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.user_data['file_id'] = update.message.document.file_id
    await update.message.reply_text('Please choose the original language:', reply_markup=reply_markup)

async def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['original_language'] = query.data
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("English (EN)", callback_data='en')],
        [InlineKeyboardButton("French (FR)", callback_data='fr')],
        [InlineKeyboardButton("Spanish (ES)", callback_data='es')],
        [InlineKeyboardButton("Arabic (AR)", callback_data='ar')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Please choose the target language:", reply_markup=reply_markup)

async def handle_translation_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['convert_to'] = query.data
    await query.answer()

    # Download the file from Telegram
    file_id = context.user_data['file_id']
    file = await context.bot.get_file(file_id)
    file_path = await file.download()

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

    await query.edit_message_text(
        text=f"Your file has been uploaded and queued for translation.\n\n[File URL]({file_url})",
        parse_mode=ParseMode.MARKDOWN
    )

# Register Bot Commands and Handlers
app_bot.add_handler(CommandHandler("start", start))
app_bot.add_handler(MessageHandler(filters.Document.MIMEType("application/vnd.openxmlformats-officedocument.wordprocessingml.document"), handle_document))
app_bot.add_handler(CallbackQueryHandler(handle_language_selection, pattern='^(en|fr|es|ar)$'))
app_bot.add_handler(CallbackQueryHandler(handle_translation_selection, pattern='^(en|fr|es|ar)$'))

# Define FastAPI route for Telegram Webhook
@app.post("/webhook")
async def process_webhook(request: Request):
    json_data = await request.json()
    update = Update.de_json(json_data, app_bot.bot)
    await app_bot.process_update(update)
    return JSONResponse(content={"status": "ok"})

# Define the FastAPI root route
@app.get("/")
def read_root():
    return {"message": "Telegram bot is running"}

# Run FastAPI application using Uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
