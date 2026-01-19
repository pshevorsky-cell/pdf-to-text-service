import logging
import os
import io
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import PyPDF2
from groq import Groq

# === Настройка логирования ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Загрузка секретов из Render ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
    raise ValueError("Укажите TELEGRAM_BOT_TOKEN и GROQ_API_KEY в Render Environment Variables")

# === Инициализация Groq ===
client = Groq(api_key=GROQ_API_KEY)

# === PROMPT — строго по вашему шаблону ===
PROMPT = """You are a logistics expert. Your ONLY task is to extract data and output EXACTLY the format below. Follow these rules strictly:

1. Output ONLY the sections shown below — nothing before, nothing after.
2. NEVER include extra text like "Rate Agreement", "Company", "Driver Name", "File #", etc.
3. For [Address Type], write "RESIDENTIAL" only if the word "RESIDENTIAL" appears in the delivery address. Otherwise, write "COMMERCIAL".
4. For MILES:
   - If the PDF explicitly states miles (e.g., "Miles: 2,559"), use that number.
   - If not, estimate the distance between pickup and delivery cities based on common U.S. geography (e.g., "New York to Los Angeles ≈ 2,800 miles").
   - If you cannot estimate, leave it blank: "MILES: ".
5. Keep weight, pieces, and rate exactly as written in the PDF.
6. NEVER add explanations, notes, or markdown.

Format:

PICK UP

[Pickup Date and Time]

[Pickup Address Lines]

DELIVERY

[Delivery Date and Time]

[Recipient Name]
[Delivery Address Lines]

WEIGHT: [weight]
PIECES: [pieces]
MILES: [miles]
TOTAL RATE: [total rate]

📒Mandatory Note:

🌎Our 24/7 tracking team will support you on this shipment and may request your current location when required by the broker. Please make sure to stay in touch with them at all times. For any questions or issues during the route, loading, or unloading, please contact us directly via messages. Permanent phone number: (484) 339-3955.

🙏And if you feel satisfied with our service, you are always welcome to add a tip by simply writing, for example: “TIPS $25”. It’s never expected but always greatly appreciated — and it goes directly to your dispatcher.

Now process the PDF text below. Output ONLY the formatted result — nothing else."""
# === Функции обработки ===
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
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": PROMPT + "\n\nText from PDF:\n" + text}],
            model="llama-3.1-8b-instant",
            temperature=0.0,
            max_tokens=1000,
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq error: {e}")
        raise

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
        logger.exception("Ошибка при обработке PDF")
        await update.message.reply_text("Не удалось обработать PDF.")

# === Запуск бота с вебхуком ===
def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.MimeType("application/pdf"), handle_pdf))
    app.add_handler(MessageHandler(filters.ALL, lambda u, c: u.message.reply_text("Отправьте PDF с Rate Confirmation.")))

    # Получаем URL из Render (он выглядит как: https://your-service.onrender.com)
    RENDER_SERVICE_NAME = os.getenv("RENDER_SERVICE_NAME", "pdf-to-text-service-1")
    WEBHOOK_URL = f"https://{RENDER_SERVICE_NAME}.onrender.com"

    port = int(os.environ.get("PORT", 10000))
    webhook_path = f"/{TELEGRAM_BOT_TOKEN}"

    logger.info(f"Setting webhook: {WEBHOOK_URL}{webhook_path}")
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=TELEGRAM_BOT_TOKEN,
        webhook_url=f"{WEBHOOK_URL}{webhook_path}"
    )

if __name__ == "__main__":
    main()
