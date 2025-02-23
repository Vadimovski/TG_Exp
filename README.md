Эта программа предназначена для экспорта сообщений из чатов Telegram. Программа позволяет: Экспортировать все сообщения из выбранных чатов/каналов в текстовый файл и автоматически обновлять экспорт.

### Для использования программы вам нужно:
1. Установить библиотеку **Telethon**.
```python
pip install telethon
```

2. Получите **API ID** и **API HASH**.

    Для этого зайдите на [my.telegram.org](my.telegram.org). Ссылка не кликабельна, поэтому скопируйте и вставьте в строку поиска. По ссылке зарегистрируйте новое приложение. Эти данные понадобятся для работы с Telegram API.

После чего можете запускать код 
```python
python ui.py
```

### **User manual**

#### При первом запуске откроется окно запроса API-данных. 

– Введите ваш **api_id** (числовое значение) и **api_hash** (строку).

– Нажмите кнопку «Сохранить».


#### На основном экране в левой части нажмите кнопку «Подключиться к Telegram».

– Если вы впервые подключаетесь, Telegram запросит ввод номера телефона (или токена бота), кода верификации и доп пароль (если он есть) для подключения к вашему аккаунту в Telegram. После успешного подключения список ваших диалогов появится в левой части окна.


#### В правой верхней панели нажмите «Выбрать директорию экспорта» и укажите папку, в которой будут сохраняться все файлы.

– В этой папке для каждого блока будет создана своя подпапка.


#### Нажмите кнопку «Добавить блок» – появится блок, в котором можно настроить экспорт для группы чатов.

– В верхнем поле блока введите название блока (например, «Рабочие чаты»).


#### Внутри блока нажмите «+ чат» для добавления нового поля.

– Введите данные чата в формате: chat_name, chat_id (например, «Общий чат, 123456789»). Или просто нажмите кнопку скопировать рядом с нужным чатом в левом списке.

#### Рядом с каждым полем для чата находится кнопка с надписью «Экспорт».

– Если для данного чата ещё не существует файла, программа выполнит экспорт (сбор всех сообщений и запись их в файл с названием чата).

– Если файл уже существует, программа не будет повторно экспортировать весь чат, а сразу зарегистрирует его для обновления. Обновление происходит раз в минуту для всех чатов, включенных в экспорт, по очереди. 
