import logging
import os
import io
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import PyPDF2
from groq import Groq

# Загрузка переменных окружения из Render Secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
    raise ValueError("Укажите TELEGRAM_BOT_TOKEN и GROQ_API_KEY в Render Secrets")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

client = Groq(api_key=GROQ_API_KEY)

PROMPT = """You are a logistics expert. Output ONLY the following format — no extra text, no explanations, no prefixes.

PICK UP

[Pickup Date and Time]

[Pickup Address Lines]

DELIVERY

[Delivery Date]
[Recipient Name]
[Delivery Address Lines]
[Address Type]

WEIGHT: [weight]
PIECES: [pieces]
MILES: [miles]
TOTAL RATE: [total rate]

📒Mandatory Note:

🌎Our 24/7 tracking team will support you on this shipment and may request your current location when required by the broker. Please make sure to stay in touch with them at all times. For any questions or issues during the route, loading, or unloading, please contact us directly via messages. Permanent phone number: (484) 339-3955.

🙏And if you feel satisfied with our service, you are always welcome to add a tip by simply writing, for example: “TIPS $25”. It’s never expected but always greatly appreciated — and it goes directly to your dispatcher."""

async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    pdf_file = io.BytesIO(pdf_bytes)
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text += t + "\n"
    return text.strip()

async def parse_with_ai(text: str) -> str:
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": PROMPT + "\n\nText from PDF:\n" + text}],
        model="llama-3.1-8b-instant",
        temperature=0.0,
        max_tokens=1000,
    )
    return chat_completion.choices[0].message.content.strip()

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_chat_action(action="typing")
        doc = update.message.document
        if doc.mime_type != "application/pdf":
            await update.message.reply_text("Пожалуйста, отправьте PDF-файл.")
            return

        file = await context.bot.get_file(doc.file_id)
        pdf_bytes = await file.download_as_bytearray()
        pdf_text = await extract_text_from_pdf(bytes(pdf_bytes))
        
        if not pdf_text:
            await update.message.reply_text("PDF не содержит текста (возможно, это скан).")
            return

        load_info = await parse_with_ai(pdf_text)
        await update.message.reply_text(load_info)

    except Exception as e:
        logger.exception("Ошибка")
        await update.message.reply_text("Не удалось обработать PDF.")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.MimeType("application/pdf"), handle_pdf))
    app.add_handler(MessageHandler(filters.ALL, lambda u, c: u.message.reply_text("Отправьте PDF.")))

    # Render использует PORT из окружения
    port = int(os.environ.get("PORT", 10000))
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=TELEGRAM_BOT_TOKEN,
        webhook_url=f"https://{os.getenv('RENDER_EXTERNAL_URL')}/{TELEGRAM_BOT_TOKEN}"
    )

if __name__ == "__main__":
    main()
