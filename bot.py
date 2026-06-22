import os
import json
import base64
import logging
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

PROMPT = """Ты эксперт по мерчандайзингу бренда ROZMETOV.
Проанализируй фото витрины холодильника и ответь ТОЛЬКО в формате JSON без лишнего текста:

{
  "score": число от 0 до 10,
  "oos": true если есть пустые места на полке иначе false,
  "shelf_share_pct": примерный процент полки занятой брендом ROZMETOV,
  "pos_present": true если видны воблеры или шелфтокеры иначе false,
  "violations": ["нарушение 1", "нарушение 2"],
  "recommendations": ["рекомендация 1", "рекомендация 2"],
  "summary": "итог в 1-2 предложения"
}

Критерии оценки:
9-10: Идеальная выкладка, полный фейсинг, POS есть, нет OOS
7-8: Хорошая выкладка, мелкие недочёты
5-6: Средне, есть нарушения которые нужно исправить
3-4: Плохая выкладка, серьёзные нарушения
0-2: Критические проблемы, требует немедленного вмешательства"""


async def analyze_photo(image_base64: str) -> dict:
    """Отправляет фото в OpenAI и получает анализ."""
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o",
                "max_tokens": 1000,
                "messages": [
                    {
                        "role": "system",
                        "content": "Ты эксперт по мерчандайзингу. Отвечай только JSON."
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": PROMPT
                            }
                        ]
                    }
                ]
            }
        )
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        # Убираем markdown-обёртку если есть
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)


def format_report(result: dict, username: str) -> str:
    """Форматирует отчёт для отправки в Telegram."""
    score = result.get("score", 0)
    
    if score >= 7:
        status = "✅ Выкладка соответствует стандарту"
    elif score >= 5:
        status = "⚠️ Есть нарушения — исправь до следующего визита"
    else:
        status = "🚨 КРИТИЧНО — требует немедленных действий"

    oos = "❌ Есть пустые места" if result.get("oos") else "✅ Нет"
    pos = "✅ Есть" if result.get("pos_present") else "❌ Отсутствуют"
    shelf = result.get("shelf_share_pct", "—")

    violations = result.get("violations", [])
    violations_text = "\n".join(f"  • {v}" for v in violations) if violations else "  • Нет"

    recs = result.get("recommendations", [])
    recs_text = "\n".join(f"  • {r}" for r in recs) if recs else "  • Нет"

    summary = result.get("summary", "")

    return f"""📊 *АНАЛИЗ ВИТРИНЫ ROZMETOV*
👤 Мерчандайзер: {username}

⭐ *Балл: {score}/10*
{status}

📋 *Статус:*
• OOS (пустые места): {oos}
• Доля полки: {shelf}%
• POS-материалы: {pos}

❌ *Нарушения:*
{violations_text}

✅ *Что сделать:*
{recs_text}

💬 {summary}"""


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фото от мерчандайзера."""
    message = update.message
    user = message.from_user
    username = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "Неизвестно"

    # Уведомляем что получили фото
    await message.reply_text("📸 Фото получено, анализирую витрину... Подожди 15 секунд.")

    try:
        # Скачиваем фото (берём максимальное качество)
        photo = message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        # Загружаем в память и конвертируем в base64
        photo_bytes = await file.download_as_bytearray()
        image_base64 = base64.b64encode(photo_bytes).decode("utf-8")

        # Анализируем через OpenAI
        result = await analyze_photo(image_base64)

        # Отправляем отчёт
        report = format_report(result, username)
        await message.reply_text(report, parse_mode="Markdown")

        logger.info(f"Проанализировано фото от {username}, балл: {result.get('score')}")

    except json.JSONDecodeError:
        await message.reply_text("⚠️ Не смог разобрать ответ от AI. Попробуй отправить фото ещё раз.")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.reply_text(f"❌ Произошла ошибка: {str(e)}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ответ на текстовые сообщения."""
    await update.message.reply_text(
        "📸 Отправь фото витрины — я проанализирую выкладку ROZMETOV и дам оценку."
    )


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
