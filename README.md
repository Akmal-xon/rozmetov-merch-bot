# Rozmetov Merch Bot

Telegram-бот для автоматического анализа витрин ROZMETOV через GPT-4o.

## Деплой на Railway (бесплатно)

1. Зайди на railway.app → New Project → Deploy from GitHub
2. Загрузи эту папку в GitHub репозиторий
3. В Railway добавь переменные окружения:
   - TELEGRAM_TOKEN = токен от BotFather
   - OPENAI_API_KEY = ключ от OpenAI
4. Railway автоматически запустит бота

## Что умеет бот

- Принимает фото витрины в Telegram
- Анализирует через GPT-4o Vision
- Выдаёт оценку 0-10
- Показывает нарушения и рекомендации
- Работает в группах и личных чатах
