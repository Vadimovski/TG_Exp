import os
import json
import threading
import asyncio
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog

from business import TelegramExporter

CONFIG_FILE = "config.json"
BLOCKS_FILE = "blocks.json"

class TelegramExporterUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Telegram Exporter")
        self.root.geometry("1920x1080")

        self.api_id = None
        self.api_hash = None
        self.export_dir = None
        self.exporter = None
        self.exporter_loop = None
        self.dialogs = []
        self.blocks = []
        self.updates = {}

        self.output_format = tk.StringVar(value="md")

        self.cred_frame = tk.Frame(root)
        self.main_frame = tk.Frame(root)

        self.setup_cred_frame()
        self.setup_main_frame()

        if self.load_config():
            self.show_main_frame()
            self.load_blocks()
        else:
            self.show_cred_frame()

    def setup_cred_frame(self):
        tk.Label(self.cred_frame, text="Введите api_id (число):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_api_id = tk.Entry(self.cred_frame)
        self.entry_api_id.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(self.cred_frame, text="Введите api_hash:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.entry_api_hash = tk.Entry(self.cred_frame)
        self.entry_api_hash.grid(row=1, column=1, padx=5, pady=5)

        tk.Button(self.cred_frame, text="Сохранить", command=self.save_credentials).grid(row=2, column=0, columnspan=2, padx=5, pady=5)

    def setup_main_frame(self):
        self.main_frame.columnconfigure(0, weight=1, minsize=600)
        self.main_frame.columnconfigure(1, weight=1, minsize=600)
        self.main_frame.rowconfigure(0, weight=1)

        self.left_frame = tk.Frame(self.main_frame, bg="lightgrey")
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.left_frame.rowconfigure(1, weight=1)
        self.left_frame.columnconfigure(0, weight=1)

        self.top_buttons_frame = tk.Frame(self.left_frame, bg="white")
        self.top_buttons_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.connect_button = tk.Button(self.top_buttons_frame, text="Подключиться к Telegram", command=self.connect)
        self.connect_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.refresh_button = tk.Button(self.top_buttons_frame, text="Обновить чаты", command=self.refresh_chats)
        self.refresh_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.status_label = tk.Label(self.top_buttons_frame, text="Статус: ожидание", bg="white")
        self.status_label.pack(side=tk.LEFT, padx=5, pady=5)

        self.canvas = tk.Canvas(self.left_frame, bg="lightgrey")
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.scrollbar = tk.Scrollbar(self.left_frame, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=1, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.dialogs_container = tk.Frame(self.canvas, bg="lightgrey")
        self.canvas.create_window((0, 0), window=self.dialogs_container, anchor="nw")
        self.dialogs_container.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.right_frame = tk.Frame(self.main_frame, bg="white")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        self.top_right_frame = tk.Frame(self.right_frame, bg="white")
        self.top_right_frame.pack(fill=tk.X, padx=5, pady=5)

        self.current_chat_label = tk.Label(self.top_right_frame, text="Текущий чат: нет активных", bg="white")
        self.current_chat_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=5)

        self.add_block_button = tk.Button(self.top_right_frame, text="Добавить блок", command=self.on_add_block)
        self.add_block_button.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        frame_format = tk.Frame(self.top_right_frame, bg="white")
        frame_format.grid(row=1, column=2, padx=5, pady=5, sticky="e")
        tk.Label(frame_format, text="Экспортировать как:", bg="white").pack(side=tk.LEFT)
        self.format_menu = tk.OptionMenu(frame_format, self.output_format, "txt", "md")
        self.format_menu.pack(side=tk.LEFT, padx=5)

        self.export_dir_button = tk.Button(self.top_right_frame, text="Директория экспорта", command=self.choose_export_dir)
        self.export_dir_button.grid(row=1, column=1, padx=5, pady=5, sticky="e")
        self.export_dir_label = tk.Label(self.top_right_frame, text="Экспорт в: (не выбран)", bg="white")
        self.export_dir_label.grid(row=2, column=1, padx=5, pady=5, sticky="e")

        self.right_canvas = tk.Canvas(self.right_frame, bg="white")
        self.right_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.right_scrollbar = tk.Scrollbar(self.right_frame, orient="vertical", command=self.right_canvas.yview)
        self.right_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_canvas.configure(yscrollcommand=self.right_scrollbar.set)
        self.blocks_container = tk.Frame(self.right_canvas, bg="white")
        self.blocks_window = self.right_canvas.create_window((0, 0), window=self.blocks_container, anchor="nw")
        self.blocks_container.bind("<Configure>", lambda e: self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all")))
        self.right_canvas.bind("<Configure>", self.on_right_canvas_configure)

    def on_right_canvas_configure(self, event):
        self.right_canvas.itemconfig(self.blocks_window, width=event.width)

    def choose_export_dir(self):
        directory = filedialog.askdirectory(initialdir=self.export_dir if self.export_dir else os.getcwd())
        if directory:
            self.export_dir = directory
            self.update_export_dir_label()
            self.save_config()

    def update_export_dir_label(self):
        self.export_dir_label.config(text=f"Экспорт в: {self.export_dir}")

    def show_cred_frame(self):
        self.main_frame.pack_forget()
        self.cred_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def show_main_frame(self):
        self.cred_frame.pack_forget()
        self.main_frame.pack(fill=tk.BOTH, expand=True)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                if "api_id" in config and "api_hash" in config:
                    self.api_id = config["api_id"]
                    self.api_hash = config["api_hash"]
                    self.export_dir = config.get("export_dir", "tg_exp")
                    self.update_export_dir_label()
                    return True
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить конфигурацию: {e}")
        return False

    def save_config(self):
        config = {"api_id": self.api_id, "api_hash": self.api_hash, "export_dir": self.export_dir}
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить конфигурацию: {e}")

    def save_credentials(self):
        api_id_input = self.entry_api_id.get().strip()
        api_hash_input = self.entry_api_hash.get().strip()
        try:
            self.api_id = int(api_id_input)
        except ValueError:
            messagebox.showerror("Ошибка", "api_id должно быть числом.")
            return
        if not api_hash_input:
            messagebox.showerror("Ошибка", "api_hash не может быть пустым.")
            return
        self.api_hash = api_hash_input
        if not self.export_dir:
            self.export_dir = "tg_exp"
        self.save_config()
        messagebox.showinfo("Успех", "Конфигурация сохранена.")
        self.show_main_frame()
        self.load_blocks()

    def connect(self):
        self.status_label.config(text="Статус: подключение...")
        self.connect_button.config(state=tk.DISABLED)
        threading.Thread(target=self.connect_thread, daemon=True).start()

    def connect_thread(self):
        self.exporter_loop = asyncio.new_event_loop()
        def run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()
        threading.Thread(target=run_loop, args=(self.exporter_loop,), daemon=True).start()

        self.exporter = TelegramExporter(self.api_id, self.api_hash)
        future = asyncio.run_coroutine_threadsafe(
            self.exporter.connect(self.get_phone, self.get_code, self.get_password),
            self.exporter_loop
        )
        try:
            self.dialogs = future.result()
            self.root.after(0, self.update_dialog_list)
            self.root.after(0, lambda: self.status_label.config(text="Статус: подключено"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка подключения: {e}"))
            self.root.after(0, lambda: self.status_label.config(text="Статус: ошибка подключения"))
            self.root.after(0, lambda: self.connect_button.config(state=tk.NORMAL))

    def refresh_chats(self):
        if self.exporter is None or self.exporter.client is None:
            messagebox.showwarning("Внимание", "Клиент не подключён. Сначала подключитесь к Telegram.")
            return
        future = asyncio.run_coroutine_threadsafe(self.exporter.client.get_dialogs(), self.exporter_loop)
        try:
            self.dialogs = future.result()
            self.root.after(0, self.update_dialog_list)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка обновления чатов: {e}"))

    def get_phone(self):
        result = [None]
        event = threading.Event()
        def ask():
            result[0] = simpledialog.askstring("Телефон", "Введите номер телефона (или токен бота):", parent=self.root)
            event.set()
        self.root.after(0, ask)
        event.wait()
        return result[0]

    def get_code(self):
        result = [None]
        event = threading.Event()
        def ask():
            result[0] = simpledialog.askstring("Код", "Введите код верификации:", parent=self.root)
            event.set()
        self.root.after(0, ask)
        event.wait()
        return result[0]

    def get_password(self):
        result = [None]
        event = threading.Event()
        def ask():
            result[0] = simpledialog.askstring("Пароль", "Введите второй пароль (если установлен):", parent=self.root, show='*')
            event.set()
        self.root.after(0, ask)
        event.wait()
        return result[0]

    def update_dialog_list(self):
        def is_chat_added(chat_id):
            for block in self.blocks:
                for entry_obj in block.chat_entries:
                    text = entry_obj["entry"].get().strip()
                    if text:
                        parts = text.split(',')
                        if len(parts) >= 2:
                            try:
                                entry_chat_id = int(parts[1].strip())
                                if entry_chat_id == chat_id:
                                    return True
                            except ValueError:
                                continue
            return False

        for widget in self.dialogs_container.winfo_children():
            widget.destroy()
        for idx, dialog in enumerate(self.dialogs):
            row_frame = tk.Frame(self.dialogs_container, bg="lightgrey")
            row_frame.pack(fill=tk.X, padx=5, pady=2)
            indicator = tk.Label(row_frame, text="✓" if is_chat_added(dialog.id) else "  ", fg="green", bg="lightgrey")
            indicator.pack(side=tk.LEFT, padx=(5,0))
            label = tk.Label(row_frame, text=f"{idx+1}. {dialog.name or 'Без названия'} (ID: {dialog.id})", bg="lightgrey")
            label.pack(side=tk.LEFT, padx=5)
            search_button = tk.Button(row_frame, text="Поиск", command=lambda d=dialog: self.search_chat_for_block(d))
            search_button.pack(side=tk.RIGHT, padx=5)
            copy_button = tk.Button(row_frame, text="Копировать чат", command=lambda d=dialog: self.copy_chat(d))
            copy_button.pack(side=tk.RIGHT, padx=5)

    def search_chat_for_block(self, dialog):
        found_blocks = []
        for block in self.blocks:
            for entry_obj in block.chat_entries:
                text = entry_obj["entry"].get().strip()
                if text:
                    parts = text.split(',')
                    if len(parts) >= 2:
                        try:
                            entry_chat_id = int(parts[1].strip())
                            if entry_chat_id == dialog.id:
                                found_blocks.append(block.name_entry.get().strip())
                        except ValueError:
                            continue
        if found_blocks:
            message = f"Чат находится в блок{'е' if len(found_blocks) == 1 else 'ах'}: {', '.join(found_blocks)}"
        else:
            message = "Чат не добавлен ни в один блок."
        messagebox.showinfo("Поиск блока", message)

    def copy_chat(self, dialog):
        chat_title = dialog.name or "Без названия"
        chat_info = f"{chat_title}, {dialog.id}"
        self.root.clipboard_clear()
        self.root.clipboard_append(chat_info)
        messagebox.showinfo("Копировать чат", f"Скопировано: {chat_info}")

    def save_all_blocks(self):
        self.save_blocks()
        messagebox.showinfo("Сохранено", "Все блоки сохранены.")

    def on_add_block(self):
        self.add_block()

    def add_block(self, initial_data=None):
        block = ChatBlock(self.blocks_container, save_callback=self.save_blocks, export_callback=self.export_single_chat, delete_callback=self.remove_block)
        if initial_data:
            block.name_entry.delete(0, tk.END)
            block.name_entry.insert(0, initial_data.get("name", ""))
            for entry_obj in block.chat_entries:
                entry_obj["frame"].destroy()
            block.chat_entries = []
            for chat in initial_data.get("chats", []):
                block.add_chat(initial_value=chat)
        block.frame.pack(fill=tk.X, padx=5, pady=5, anchor="n")
        self.blocks.append(block)
        self.save_blocks()

    def remove_block(self, block):
        if block in self.blocks:
            self.blocks.remove(block)
            block.frame.destroy()
            self.save_blocks()

    def save_blocks(self):
        blocks_data = [block.get_data() for block in self.blocks]
        try:
            with open(BLOCKS_FILE, "w", encoding="utf-8") as f:
                json.dump(blocks_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить блоки: {e}")

    def load_blocks(self):
        if os.path.exists(BLOCKS_FILE):
            try:
                with open(BLOCKS_FILE, "r", encoding="utf-8") as f:
                    blocks_data = json.load(f)
                for block_data in blocks_data:
                    self.add_block(initial_data=block_data)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить блоки: {e}")

    def export_single_chat(self, chat_value, block_name, chat_entry_obj):
        if not chat_value:
            messagebox.showwarning("Внимание", "Чат не указан.")
            return
        parts = chat_value.split(',')
        if len(parts) != 2:
            messagebox.showwarning("Внимание", "Введите данные в формате 'chat_name,chat_id'.")
            return
        chat_name = parts[0].strip()
        try:
            chat_id = int(parts[1].strip())
        except ValueError:
            messagebox.showwarning("Внимание", "chat_id должно быть числом.")
            return

        key = (block_name, chat_name, chat_id)
        if chat_entry_obj["active"]:
            if key in self.updates:
                del self.updates[key]
                if str(chat_id) in self.exporter.exported_chats:
                    del self.exporter.exported_chats[str(chat_id)]
                    self.exporter.save_exported_chats()
            chat_entry_obj["active"] = False
            chat_entry_obj["button"].config(text="Экспорт")
            self.root.after(0, lambda: self.current_chat_label.config(text="Текущий чат: нет активных"))
            return

        export_dir = os.path.join(self.export_dir, block_name)
        os.makedirs(export_dir, exist_ok=True)
        ext = "md" if self.output_format.get() == "md" else "txt"
        base_file_path = os.path.join(export_dir, f"{chat_name}.{ext}")

        if self.exporter is None or self.exporter.client is None:
            messagebox.showwarning("Внимание", "Клиент не подключён. Сначала подключитесь к Telegram.")
            return

        self.exporter.add_to_queue(chat_id, base_file_path)
        self.updates[key] = {"file_path": base_file_path}
        chat_entry_obj["active"] = True
        self.root.after(0, lambda: chat_entry_obj["button"].config(text="Закончить экспорт"))
        self.root.after(0, lambda: self.current_chat_label.config(text=f"Текущий чат: добавлен {chat_name} (ID: {chat_id})"))

        if not self.exporter.running:
            threading.Thread(target=self.exporter.start_export, args=(self.exporter_loop,), daemon=True).start()

class ChatBlock:
    def __init__(self, parent, save_callback, export_callback, delete_callback=None):
        self.frame = tk.Frame(parent, bg="lightblue", bd=2, relief=tk.RIDGE)
        self.save_callback = save_callback
        self.export_callback = export_callback
        self.delete_callback = delete_callback
        tk.Label(self.frame, text="Название блока:", bg="lightblue").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.name_entry = tk.Entry(self.frame)
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.frame.columnconfigure(1, weight=1)

        self.chat_container = tk.Frame(self.frame, bg="lightblue")
        self.chat_container.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        self.chat_entries = []
        self.add_chat()

        self.control_frame = tk.Frame(self.frame, bg="lightblue")
        self.control_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        self.add_chat_button = tk.Button(self.control_frame, text="+ чат", command=self.add_chat)
        self.add_chat_button.pack(side=tk.LEFT, padx=5)
        self.save_block_button = tk.Button(self.control_frame, text="Сохранить блок", command=self.save_block)
        self.save_block_button.pack(side=tk.LEFT, padx=5)
        self.delete_block_button = tk.Button(self.control_frame, text="Удалить блок", command=self.delete_block)
        self.delete_block_button.pack(side=tk.RIGHT, padx=5)
        self.remove_empty_button = tk.Button(self.control_frame, text="Убрать пустые поля", command=self.remove_empty_fields)
        self.remove_empty_button.pack(side=tk.RIGHT, padx=5)

    def add_chat(self, initial_value=""):
        chat_frame = tk.Frame(self.chat_container, bg="lightblue")
        chat_frame.pack(fill=tk.X, pady=2)
        entry = tk.Entry(chat_frame, width=30)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        entry.insert(0, initial_value)
        entry_obj = {
            "frame": chat_frame,
            "entry": entry,
            "button": None,
            "active": False
        }
        export_button = tk.Button(chat_frame, text="Экспорт", command=lambda: self.export_chat(entry, entry_obj))
        export_button.pack(side=tk.LEFT)
        entry_obj["button"] = export_button
        self.chat_entries.append(entry_obj)
        self.save_callback()

    def get_data(self):
        block_name = self.name_entry.get().strip()
        chats = [entry_obj["entry"].get() for entry_obj in self.chat_entries]
        return {"name": block_name, "chats": chats}

    def save_block(self):
        self.save_callback()
        messagebox.showinfo("Сохранено", f"Блок '{self.name_entry.get()}' сохранён с {len(self.chat_entries)} полями.")

    def delete_block(self):
        if self.delete_callback:
            self.delete_callback(self)
        self.frame.destroy()

    def remove_empty_fields(self):
        new_entries = []
        for entry_obj in self.chat_entries:
            if entry_obj["entry"].get().strip() == "":
                entry_obj["frame"].destroy()
            else:
                new_entries.append(entry_obj)
        self.chat_entries = new_entries
        self.save_callback()

    def export_chat(self, entry, entry_obj):
        chat_value = entry.get().strip()
        self.export_callback(chat_value, self.name_entry.get().strip(), entry_obj)

if __name__ == "__main__":
    root = tk.Tk()
    app = TelegramExporterUI(root)
    root.mainloop()