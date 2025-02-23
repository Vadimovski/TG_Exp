import asyncio
import os
from telethon import TelegramClient

CHUNK_SIZE = 5000

def chunk_messages(messages, chunk_size):
    """Разбивает список сообщений на чанки с разделителями."""
    if not messages:
        return []
    chunked = []
    for i in range(0, len(messages), chunk_size):
        chunked.extend(messages[i:i+chunk_size])
        if i + chunk_size < len(messages):
            chunked.append("---- CHUNK BREAK ----\n")
    return chunked

class TelegramExporter:
    def __init__(self, api_id, api_hash, session_name="session_name"):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = None

    async def connect(self, phone_callback, code_callback, password_callback=None):
        """
        Подключается к Telegram, используя колбэки для запроса номера телефона,
        кода верификации и, при необходимости, второго пароля.
        """
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        await self.client.start(
            phone=phone_callback,
            code_callback=code_callback,
            password=password_callback
        )
        return await self.client.get_dialogs()

    async def export_chat(self, chat_id, base_file_path):
        messages = []
        max_id = 0
        async for message in self.client.iter_messages(chat_id):
            if message.id > max_id:
                max_id = message.id
            date_str = message.date.strftime('%Y-%m-%d %H:%M:%S') if message.date else "UnknownDate"
            sender = message.sender_id if message.sender_id else "UnknownSender"
            text = message.message if message.message else ""
            messages.append(f"MSGID: {message.id} | [{date_str}] (ID {sender}): {text}\n")
        chunked = chunk_messages(messages, CHUNK_SIZE)
        with open(base_file_path, "w", encoding="utf-8") as f:
            for line in chunked:
                f.write(line)
        return max_id

    async def update_chat(self, chat_id, base_file_path, last_message_id):
        new_messages = []
        new_last_id = last_message_id
        async for message in self.client.iter_messages(chat_id, min_id=last_message_id):
            if message.id > new_last_id:
                new_last_id = message.id
            date_str = message.date.strftime('%Y-%m-%d %H:%M:%S') if message.date else "UnknownDate"
            sender = message.sender_id if message.sender_id else "UnknownSender"
            text = message.message if message.message else ""
            new_messages.append(f"MSGID: {message.id} | [{date_str}] (ID {sender}): {text}\n")
        if new_messages:
            if os.path.exists(base_file_path):
                with open(base_file_path, "r", encoding="utf-8") as f:
                    old_content = f.read()
            else:
                old_content = ""
            updated = chunk_messages(new_messages, CHUNK_SIZE)
            with open(base_file_path, "w", encoding="utf-8") as f:
                for line in updated:
                    f.write(line)
                f.write(old_content)
        return new_last_id
