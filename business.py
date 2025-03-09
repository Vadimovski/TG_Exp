import asyncio
import os
import json
from telethon import TelegramClient
from telethon.errors import FloodWaitError

def load_config(config_file="config.json"):
    print(f"Загрузка конфигурации из {config_file}...")
    default_config = {
        "api_id": 12345,  # Замените на ваш api_id
        "api_hash": "your_api_hash",  # Замените на ваш api_hash
        "session_name": "session_name",
        "max_concurrent_chats": 2,
        "messages_limit": 200,
        "batch_delay": 1.0,
        "chat_delay": 5,
        "exported_chats_file": "exported_chats.json"
    }
    if not os.path.exists(config_file):
        print(f"Файл {config_file} не найден, создаём с значениями по умолчанию.")
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=4)
        return default_config
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        print("Конфигурация успешно загружена:", config)
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
        return config
    except json.JSONDecodeError as e:
        print(f"Ошибка в формате JSON в {config_file}: {e}. Используем значения по умолчанию.")
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=4)
        return default_config
    except Exception as e:
        print(f"Неизвестная ошибка при загрузке {config_file}: {e}. Используем значения по умолчанию.")
        return default_config

CONFIG = load_config()
API_ID = CONFIG.get("api_id")
API_HASH = CONFIG.get("api_hash")
SESSION_NAME = CONFIG.get("session_name")
MAX_CONCURRENT_CHATS = CONFIG.get("max_concurrent_chats")
MESSAGES_LIMIT = CONFIG.get("messages_limit")
BATCH_DELAY = CONFIG.get("batch_delay")
CHAT_DELAY = CONFIG.get("chat_delay")
EXPORTED_CHATS_FILE = CONFIG.get("exported_chats_file")

class TelegramExporter:
    def __init__(self, api_id=API_ID, api_hash=API_HASH, session_name=SESSION_NAME):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = None
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHATS)
        self.exported_chats = {}  # Очередь пуста при старте
        self.running = False
        self.loop = None

    def save_exported_chats(self):
        print(f"Сохранение данных о {len(self.exported_chats)} чатах в {EXPORTED_CHATS_FILE}...")
        try:
            with open(EXPORTED_CHATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.exported_chats, f, ensure_ascii=False, indent=4)
            print("Данные успешно сохранены.")
        except Exception as e:
            print(f"Ошибка сохранения {EXPORTED_CHATS_FILE}: {e}")

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
                if not chunk:
                    print(f"Сообщения для чата {chat_id} загружены, всего: {len(messages)}.")
                    break
                messages.extend(chunk)
                offset_id = chunk[-1].id
                print(f"Загружено {len(chunk)} сообщений, новый offset_id={offset_id}, всего: {len(messages)}.")
                await asyncio.sleep(BATCH_DELAY)
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
                if not lines:
                    print(f"Файл {file_path} пуст.")
                    return None, None
                first_line = lines[0].strip()
                if first_line.startswith("### Message"):  # Markdown
                    msg_id = int(first_line.split("### Message")[1].strip())
                    msg_text = lines[4].strip() if len(lines) > 4 else ""
                elif first_line.startswith("MSGID:"):  # TXT
                    parts = first_line.split("|", 1)
                    msg_id = int(parts[0].replace("MSGID:", "").strip())
                    msg_text = parts[1].strip() if len(parts) > 1 else ""
                else:
                    print(f"Некорректный формат файла {file_path}.")
                    return None, None
                print(f"Найдено последнее сообщение: ID={msg_id}, текст='{msg_text}'.")
                return msg_id, msg_text
        except Exception as e:
            print(f"Ошибка чтения файла {file_path}: {e}")
            return None, None

    async def export_chat(self, chat_id, file_path, output_format="txt"):
        file_path = os.path.normpath(file_path)
        print(f"Начало экспорта чата {chat_id} в {file_path} (формат: {output_format})...")
        if not self.client.is_connected():
            print(f"Клиент не подключён для чата {chat_id}, попытка переподключения...")
            await self.client.connect()

        chat_key = str(chat_id)
        chat_data = self.exported_chats.get(chat_key, {})
        last_id = chat_data.get("last_message_id", 0)
        last_text = chat_data.get("last_message_text", "")

        file_last_id, file_last_text = self.get_last_message_from_file(file_path)
        if file_last_id == last_id and file_last_text == last_text and last_id > 0:
            print(f"Чат {chat_id} уже обновлён, новых сообщений нет.")
            return

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
                if output_format == "md":
                    msg_content = (
                        f"### Message {message.id}\n"
                        f"**Date:** {date_str}  \n"
                        f"**Sender:** {sender}\n\n"
                        f"{text}\n\n"
                        f"---\n"
                    )
                else:
                    msg_content = f"MSGID: {message.id} | [{date_str}] (ID {sender}): {text}\n"
                messages.append(msg_content)

            if messages:
                print(f"Подготовка к записи {len(messages)} новых сообщений в файл {file_path}...")
                directory = os.path.dirname(file_path)
                if directory and not os.path.exists(directory):
                    print(f"Директория {directory} не существует, создание директории...")
                    os.makedirs(directory, exist_ok=True)
                    print(f"Директория {directory} успешно создана.")

                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        old_content = f.read()
                else:
                    old_content = ""

                try:
                    print(f"Открытие файла {file_path} для записи...")
                    with open(file_path, "w", encoding="utf-8") as f:
                        print(f"Запись данных в файл {file_path}...")
                        f.write("".join(messages))
                        f.write(old_content)
                    print(f"Файл {file_path} успешно записан.")
                    last_message_text = messages[0].split("|", 1)[1].strip() if output_format == "txt" else chat_messages[0].message or ""
                except Exception as e:
                    print(f"Ошибка при записи в файл {file_path}: {type(e).__name__}: {e}")
                    return
            else:
                print(f"Новых сообщений для чата {chat_id} нет.")
                last_message_text = last_text

            self.exported_chats[chat_key] = {
                "chat_id": chat_id,
                "file_path": file_path,
                "last_message_id": max_id,
                "last_message_text": last_message_text
            }
            self.save_exported_chats()

        print(f"Экспорт чата {chat_id} завершён, последний ID={max_id}. Ожидание {CHAT_DELAY} сек...")
        await asyncio.sleep(CHAT_DELAY)

    async def export_queue(self):
        self.running = True
        while self.running:
            if not self.exported_chats:
                await asyncio.sleep(1)
                continue
            for chat_id_str in list(self.exported_chats.keys()):
                if not self.running:
                    break
                chat_id = int(chat_id_str)
                file_path = self.exported_chats[chat_id_str]["file_path"]
                output_format = "md" if file_path.endswith(".md") else "txt"
                await self.export_chat(chat_id, file_path, output_format)
            if self.running and self.exported_chats:
                print("Очередь обработана, начинаем заново...")
            await asyncio.sleep(1)

    def start_export(self, loop):
        self.loop = loop
        if not self.running:
            asyncio.run_coroutine_threadsafe(self.export_queue(), self.loop)

    def stop_export(self):
        self.running = False

    def add_to_queue(self, chat_id, file_path):
        chat_key = str(chat_id)
        self.exported_chats[chat_key] = {
            "chat_id": chat_id,
            "file_path": file_path,
            "last_message_id": 0,
            "last_message_text": ""
        }
        self.save_exported_chats()