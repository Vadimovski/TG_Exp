import os
import asyncio
from telethon import TelegramClient

# Вставьте свои данные API
api_id = YOUR_API_ID       # Например: 123456
api_hash = 'YOUR_API_HASH'
session_name = 'session_name'  # Название файла сессии

client = TelegramClient(session_name, api_id, api_hash)

async def choose_and_export():
    # Получаем список диалогов (чаты, группы, каналы)
    dialogs = await client.get_dialogs()
    
    # Вывод списка чатов/каналов с нумерацией
    print("Список доступных чатов и каналов:")
    for idx, dialog in enumerate(dialogs):
        chat_title = dialog.name or "Без названия"
        print(f"{idx + 1}. {chat_title} (ID: {dialog.id})")
    
    # Запрашиваем у пользователя номера чатов/каналов для экспорта
    selection = input("Введите номера чатов/каналов, которые хотите экспортировать (через запятую): ")
    
    # Обработка ввода: преобразование строк в индексы списка
    try:
        selected_indexes = [int(num.strip()) - 1 for num in selection.split(",")]
    except Exception as e:
        print("Ошибка ввода. Пожалуйста, введите корректные номера через запятую.")
        return

    # Экспорт сообщений для каждого выбранного диалога
    for index in selected_indexes:
        if index < 0 or index >= len(dialogs):
            print(f"Номер {index + 1} вне диапазона списка.")
            continue
        
        dialog = dialogs[index]
        chat_title = dialog.name or "Без названия"
        chat_id = dialog.id
        # Формирование безопасного имени файла (убираем недопустимые символы)
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in chat_title)
        file_name = f"{safe_title}_{chat_id}.txt"
        
        print(f"Экспорт сообщений из '{chat_title}' в файл {file_name}")
        
        with open(file_name, "w", encoding="utf-8") as f:
            # Перебираем сообщения в выбранном диалоге
            async for message in client.iter_messages(dialog.id):
                # Форматирование даты и получение информации об отправителе
                date_str = message.date.strftime('%Y-%m-%d %H:%M:%S') if message.date else "UnknownDate"
                sender = message.sender_id if message.sender_id else "UnknownSender"
                text = message.message if message.message else ""
                f.write(f"[{date_str}] (ID {sender}): {text}\n")

with client:
    client.loop.run_until_complete(choose_and_export())
