# Телеграм бот ЭмБио

## Description

Телеграм бот ЭмБио - это виртуальный помощник, который всегда будет на связи с пациентом. Он поддержит, напомнит о процедуре, поделится полезными материалами и ответит на вопросы, предоставляя пользователю ощущение заботы и внимания.

## Get started

1. **Подготовка окружения:**
   - Токен и другие конфигурационные данные для запуска бота должны быть прописаны в скрытом `.env` файле.
   - Все необходимые библиотеки указаны в файле `requirements.txt`.

2. **Создание файла `.env`:**
   В корневой директории проекта создайте файл `.env` и добавьте в него следующие строки:

   ```plaintext
   TOKEN = “Токен телеграм бота”
   USERNAME_CRM = “Имя пользователя в CRM”
   PASSWORD_CRM = “Пароль пользователя в CRM”
   URL = “Ссылка на точку входа в CRM”
   POSTGRES_USER = your_postgres_user
   POSTGRES_PASSWORD = your_postgres_password
   POSTGRES_DB = your_postgres_db
   POSTGRES_HOST = your_postgres_host
   REDIS_HOST = “ip адрес сервера redis”
   REDIS_PORT = “порт сервера redis”
   REDIS_URL = “ссылка вида redis://REDIS_PASSWORD:@REDIS_HOST:REDIS_PORT/0”
   REDIS_PASSWORD = “Пароль от redis”
   SUPPORT_GROUP_ID = “Айди супергруппы поддержки, начинающиеся с -100”
   ```

3. **Устанока зависимостей:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Запуск бота**

   ```bash
   python run.py
   ```


### Json structure

#### Types of possible content in a scenario

* text - обычный текст, без медиаматериала
* image - фотоматериал
* video - видеоматериал
* text image - текстовый материал + фото для общей отправки
* text video - текстовый материал + видео для общей отправки
* survey - опрос


