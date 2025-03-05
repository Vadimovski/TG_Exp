import asyncio
import os
import json
from telethon import TelegramClient
from telethon.errors import FloodWaitError

CHUNK_SIZE = 5000
MAX_CONCURRENT_CHATS = 2
MESSAGE_DELAY = 0.25
CHAT_DELAY = 5
MESSAGES_LIMIT = 2000
EXPORTED_CHATS_FILE = "exported_chats.json"

def chunk_messages(messages, chunk_size):
    if not messages:
        return []
    chunked = []
    for i in range(0, len(messages), chunk_size):
        chunked.extend(messages[i:i + chunk_size])
        if i + chunk_size < len(messages):
            chunked.append("---- CHUNK BREAK ----\n")
    return chunked

class TelegramExporter:
    def __init__(self, api_id, api_hash, session_name="session_name"):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = None
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHATS)
        self.exported_chats = self.load_exported_chats()

    def load_exported_chats(self):
        print("Загрузка данных о чатах из exported_chats.json...")
        if os.path.exists(EXPORTED_CHATS_FILE):
            try:
                with open(EXPORTED_CHATS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"Успешно загружено: {len(data)} чатов.")
                return data
            except Exception as e:
                print(f"Ошибка загрузки exported_chats.json: {e}")
        print("Файл exported_chats.json не найден, начинаем с пустого списка.")
        return {}

    def save_exported_chats(self):
        print(f"Сохранение данных о {len(self.exported_chats)} чатах в exported_chats.json...")
        try:
            with open(EXPORTED_CHATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.exported_chats, f, ensure_ascii=False, indent=4)
            print("Данные успешно сохранены.")
        except Exception as e:
            print(f"Ошибка сохранения exported_chats.json: {e}")

    async def connect(self, phone_callback, code_callback, password_callback=None):
        print("Подключение к Telegram...")
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        await self.client.start(
            phone=phone_callback,
            code_callback=code_callback,
            password=password_callback
        )
        dialogs = await self.client.get_dialogs()
        print(f"Подключение успешно, получено {len(dialogs)} диалогов.")
        return dialogs

    async def safe_iter_messages(self, chat_id, min_id=None):
        print(f"Загрузка сообщений из чата {chat_id} с min_id={min_id}...")
        messages = []
        offset_id = 0
        while True:
            try:
                print(f"Запрос сообщений с offset_id={offset_id}, limit={MESSAGES_LIMIT}...")
                chunk = []
                async for msg in self.client.iter_messages(
                    chat_id, limit=MESSAGES_LIMIT, offset_id=offset_id, min_id=min_id
                ):
                    print(f"Получено сообщение ID={msg.id}")
                    if min_id and msg.id <= min_id:
                        print(f"Достигнут min_id={min_id}, остановка загрузки.")
                        break
                    chunk.append(msg)
                    await asyncio.sleep(MESSAGE_DELAY)
                if not chunk:
                    print(f"Сообщения для чата {chat_id} загружены, всего: {len(messages)}.")
                    break
                messages.extend(chunk)
                offset_id = chunk[-1].id
                print(f"Загружено {len(chunk)} сообщений, новый offset_id={offset_id}.")
            except FloodWaitError as e:
                wait_time = e.seconds + 5
                print(f"FloodWaitError: Ждём {wait_time} секунд перед повтором для чата {chat_id}...")
                await asyncio.sleep(wait_time)
            except Exception as e:
                print(f"Ошибка при загрузке сообщений из чата {chat_id}: {type(e).__name__}: {e}")
                break
        print(f"Завершение загрузки сообщений для чата {chat_id}, итого: {len(messages)}.")
        return messages

    def get_last_message_from_file(self, file_path):
        print(f"Проверка последнего сообщения в файле {file_path}...")
        if not os.path.exists(file_path):
            print(f"Файл {file_path} не существует.")
            return None, None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines[0].startswith("### Message"):  # Markdown
                    msg_id = int(lines[0].split("### Message")[1].strip())
                    msg_text = lines[4].strip()
                else:  # TXT
                    for line in lines:
                        if line.startswith("MSGID:"):
                            parts = line.split("|", 1)
                            msg_id = int(parts[0].replace("MSGID:", "").strip())
                            msg_text = parts[1].strip() if len(parts) > 1 else ""
                            break
                    else:
                        return None, None
                print(f"Найдено последнее сообщение: ID={msg_id}, текст='{msg_text}'.")
                return msg_id, msg_text
        except Exception as e:
            print(f"Ошибка чтения файла {file_path}: {e}")
        return None, None

    async def export_chat(self, chat_id, base_file_path):
        base_file_path = os.path.normpath(base_file_path)
        print(f"Начало экспорта чата {chat_id} в {base_file_path}...")
        if not self.client.is_connected():
            print(f"Клиент не подключён для чата {chat_id}, попытка переподключения...")
            await self.client.connect()

        chat_key = str(chat_id)
        chat_data = self.exported_chats.get(chat_key, {})
        last_id = chat_data.get("last_message_id", 0)
        last_text = chat_data.get("last_message_text", "")

        file_last_id, file_last_text = self.get_last_message_from_file(base_file_path)
        if file_last_id == last_id and file_last_text == last_text and last_id > 0:
            print(f"Чат {chat_id} уже обновлён, новых сообщений нет.")
            return last_id

        messages = []
        max_id = last_id

        async with self.semaphore:
            print(f"Получение новых сообщений для чата {chat_id}...")
            chat_messages = await self.safe_iter_messages(chat_id, min_id=last_id)
            print(f"Обработка полученных сообщений для чата {chat_id}...")
            for message in chat_messages:
                if message.id > max_id:
                    max_id = message.id
                date_str = message.date.strftime('%Y-%m-%d %H:%M:%S') if message.date else "UnknownDate"
                sender = message.sender_id if message.sender_id else "UnknownSender"
                text = message.message if message.message else ""
                messages.append(f"MSGID: {message.id} | [{date_str}] (ID {sender}): {text}\n")

            if messages:
                print(f"Подготовка к записи {len(messages)} новых сообщений в файл {base_file_path}...")
                chunked = chunk_messages(messages, CHUNK_SIZE)
                directory = os.path.dirname(base_file_path)
                if directory and not os.path.exists(directory):
                    print(f"Директория {directory} не существует, создание директории...")
                    try:
                        os.makedirs(directory, exist_ok=True)
                        print(f"Директория {directory} успешно создана.")
                    except Exception as e:
                        print(f"Ошибка создания директории {directory}: {e}")
                        return max_id

                try:
                    print(f"Открытие файла {base_file_path} для записи...")
                    with open(base_file_path, "w", encoding="utf-8") as f:
                        print(f"Запись данных в файл {base_file_path}...")
                        for line in chunked:
                            f.write(line)
                    print(f"Файл {base_file_path} успешно записан.")
                    last_message_text = messages[0].split("|", 1)[1].strip()
                except Exception as e:
                    print(f"Ошибка при записи в файл {base_file_path}: {type(e).__name__}: {e}")
                    return max_id
            else:
                print(f"Новых сообщений для чата {chat_id} нет, файл не создаётся.")
                last_message_text = last_text

            self.exported_chats[chat_key] = {
                "chat_id": chat_id,
                "file_path": base_file_path,
                "last_message_id": max_id,
                "last_message_text": last_message_text
            }
            self.save_exported_chats()

        print(f"Экспорт чата {chat_id} завершён, последний ID={max_id}. Ожидание {CHAT_DELAY} сек...")
        await asyncio.sleep(CHAT_DELAY)
        return max_id

    async def export_chat_md(self, chat_id, base_file_path):
        base_file_path = os.path.normpath(base_file_path)
        print(f"Начало экспорта чата {chat_id} в формате Markdown в {base_file_path}...")
        if not self.client.is_connected():
            print(f"Клиент не подключён для чата {chat_id}, попытка переподключения...")
            await self.client.connect()

        chat_key = str(chat_id)
        chat_data = self.exported_chats.get(chat_key, {})
        last_id = chat_data.get("last_message_id", 0)
        last_text = chat_data.get("last_message_text", "")

        file_last_id, file_last_text = self.get_last_message_from_file(base_file_path)
        if file_last_id == last_id and file_last_text == last_text and last_id > 0:
            print(f"Чат {chat_id} уже обновлён (MD), новых сообщений нет.")
            return last_id

        messages = []
        max_id = last_id

        async with self.semaphore:
            print(f"Получение новых сообщений для чата {chat_id}...")
            chat_messages = await self.safe_iter_messages(chat_id, min_id=last_id)
            print(f"Обработка полученных сообщений для чата {chat_id}...")
            for message in chat_messages:
                if message.id > max_id:
                    max_id = message.id
                date_str = message.date.strftime('%Y-%m-%d %H:%M:%S') if message.date else "UnknownDate"
                sender = message.sender_id if message.sender_id else "UnknownSender"
                text = message.message if message.message else ""
                msg_md = (
                    f"### Message {message.id}\n"
                    f"**Date:** {date_str}  \n"
                    f"**Sender:** {sender}\n\n"
                    f"{text}\n\n"
                    f"---\n"
                )
                messages.append(msg_md)

            if messages:
                print(f"Подготовка к записи {len(messages)} новых сообщений в файл {base_file_path}...")
                content = "\n".join(messages)
                directory = os.path.dirname(base_file_path)
                if directory and not os.path.exists(directory):
                    print(f"Директория {directory} не существует, создание директории...")
                    try:
                        os.makedirs(directory, exist_ok=True)
                        print(f"Директория {directory} успешно создана.")
                    except Exception as e:
                        print(f"Ошибка создания директории {directory}: {e}")
                        return max_id

                try:
                    print(f"Открытие файла {base_file_path} для записи...")
                    with open(base_file_path, "w", encoding="utf-8") as f:
                        print(f"Запись данных в файл {base_file_path}...")
                        f.write(content)
                    print(f"Файл {base_file_path} успешно записан.")
                    last_message_text = chat_messages[0].message if chat_messages else last_text
                except Exception as e:
                    print(f"Ошибка при записи в файл {base_file_path}: {type(e).__name__}: {e}")
                    return max_id
            else:
                print(f"Новых сообщений для чата {chat_id} нет, файл не создаётся.")
                last_message_text = last_text

            self.exported_chats[chat_key] = {
                "chat_id": chat_id,
                "file_path": base_file_path,
                "last_message_id": max_id,
                "last_message_text": last_message_text
            }
            self.save_exported_chats()

        print(f"Экспорт чата {chat_id} (MD) завершён, последний ID={max_id}. Ожидание {CHAT_DELAY} сек...")
        await asyncio.sleep(CHAT_DELAY)
        return max_id

    async def update_chat(self, chat_id, base_file_path, last_message_id):
        base_file_path = os.path.normpath(base_file_path)
        print(f"Начало обновления чата {chat_id} в {base_file_path}...")
        if not self.client.is_connected():
            print(f"Клиент не подключён для чата {chat_id}, попытка переподключения...")
            await self.client.connect()

        chat_key = str(chat_id)
        chat_data = self.exported_chats.get(chat_key, {})
        last_text = chat_data.get("last_message_text", "")

        file_last_id, file_last_text = self.get_last_message_from_file(base_file_path)
        if file_last_id == last_message_id and file_last_text == last_text and last_message_id > 0:
            print(f"Чат {chat_id} уже обновлён, новых сообщений нет.")
            return last_message_id

        new_messages = []
        new_last_id = last_message_id

        async with self.semaphore:
            print(f"Получение новых сообщений для чата {chat_id}...")
            chat_messages = await self.safe_iter_messages(chat_id, min_id=last_message_id)
            print(f"Обработка полученных сообщений для чата {chat_id}...")
            for message in chat_messages:
                if message.id > new_last_id:
                    new_last_id = message.id
                date_str = message.date.strftime('%Y-%m-%d %H:%M:%S') if message.date else "UnknownDate"
                sender = message.sender_id if message.sender_id else "UnknownSender"
                text = message.message if message.message else ""
                new_messages.append(f"MSGID: {message.id} | [{date_str}] (ID {sender}): {text}\n")

            if new_messages:
                print(f"Подготовка к записи {len(new_messages)} новых сообщений в файл {base_file_path}...")
                if os.path.exists(base_file_path):
                    with open(base_file_path, "r", encoding="utf-8") as f:
                        old_content = f.read()
                else:
                    old_content = ""
                updated = chunk_messages(new_messages, CHUNK_SIZE)
                try:
                    print(f"Открытие файла {base_file_path} для записи...")
                    with open(base_file_path, "w", encoding="utf-8") as f:
                        print(f"Запись данных в файл {base_file_path}...")
                        for line in updated:
                            f.write(line)
                        f.write(old_content)
                    print(f"Файл {base_file_path} успешно записан.")
                    last_message_text = new_messages[0].split("|", 1)[1].strip()
                except Exception as e:
                    print(f"Ошибка при записи в файл {base_file_path}: {type(e).__name__}: {e}")
                    return new_last_id
            else:
                print(f"Новых сообщений для чата {chat_id} нет, файл не создаётся.")
                last_message_text = last_text

            self.exported_chats[chat_key] = {
                "chat_id": chat_id,
                "file_path": base_file_path,
                "last_message_id": new_last_id,
                "last_message_text": last_message_text
            }
            self.save_exported_chats()

        print(f"Обновление чата {chat_id} завершено, последний ID={new_last_id}. Ожидание {CHAT_DELAY} сек...")
        await asyncio.sleep(CHAT_DELAY)
        return new_last_id

    async def export_multiple_chats(self, chat_list, output_format="txt"):
        print(f"Начало экспорта {len(chat_list)} чатов в формате {output_format}...")
        tasks = []
        for chat_id, file_path in chat_list:
            file_path = os.path.normpath(file_path)
            print(f"Добавление чата {chat_id} в очередь экспорта с файлом {file_path}...")
            if output_format == "md":
                task = asyncio.create_task(self.export_chat_md(chat_id, file_path))
            else:
                task = asyncio.create_task(self.export_chat(chat_id, file_path))
            tasks.append(task)
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"Ошибка в процессе экспорта: {e}")
        print("Экспорт всех чатов завершён.")

if __name__ == "__main__":
    async def main():
        exporter = TelegramExporter(api_id=12345, api_hash="your_api_hash")
        dialogs = await exporter.connect(
            lambda: input("Введите номер телефона: "),
            lambda: input("Введите код: "),
            lambda: input("Введите пароль (если требуется): ")
        )
        chat_list = [(dialog.id, f"chat_{dialog.id}.md") for dialog in dialogs[:3]]
        await exporter.export_multiple_chats(chat_list, output_format="md")

    asyncio.run(main())