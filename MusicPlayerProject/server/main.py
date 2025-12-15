from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
import re

from . import models, schemas, repositories, database, auth


models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    version="1.0.0",
    docs_url=None,
    redoc_url="/",
    title="Music Player API",
    description="""
    API для музыкального плеера с полным набором функций:
    
    🔐 **Аутентификация** - JWT-based регистрация и вход
    🎵 **Управление музыкой** - добавление, удаление и воспроизведение песен
    📊 **Аналитика** - статистика прослушиваний и активности пользователей
    💬 **Real-time чат** - WebSocket-чат между пользователями
    📈 **Логирование** - отслеживание действий пользователей
    
    ## Основные возможности:
    
    1. **Регистрация и аутентификация** пользователей
    2. **Добавление песен** в общий или личный плейлист
    3. **Воспроизведение музыки** с записью статистики
    4. **Получение аналитики** по прослушиваниям и активности
    5. **Real-time общение** через WebSocket-чат
    6. **Логирование действий** для администрирования
    
    ## Требования к учетным данным:
    
    - Логин: минимум 6 символов, только буквы, цифры и подчеркивание
    - Пароль: минимум 6 символов, только буквы, цифры и подчеркивание
    
    ## База данных:
    
    - Используется SQLite с SQLAlchemy ORM
    - Автоматическое создание таблиц при запуске
    - Поддерживает пользователей, песни, историю прослушиваний и чат
    """,

)

class ConnectionManager:
    """
    Менеджер WebSocket соединений для чата.
    
    Отслеживает активные подключения и обеспечивает широковещательную рассылку сообщений.
    
    Атрибуты:
        active_connections (List[WebSocket]): Список активных WebSocket-соединений
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """
        Принимает новое WebSocket соединение.
        
        Args:
            websocket (WebSocket): Новое WebSocket-соединение
        """
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """
        Отключает WebSocket соединение.
        
        Args:
            websocket (WebSocket): Соединение для отключения
        """
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass

    async def broadcast(self, message: str):
        """
        Отправляет сообщение всем активным соединениям.
        
        Args:
            message (str): Сообщение для отправки
        """
        to_remove = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                to_remove.append(connection)
        for c in to_remove:
            self.disconnect(c)


manager = ConnectionManager()

@app.post("/auth/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    """
    Регистрация нового пользователя в системе.
    
    ## Описание:
    
    Создает нового пользователя с указанными учетными данными.
    Производит валидацию логина и пароля согласно требованиям безопасности.
    После успешной регистрации автоматически логирует действие в системе.
    
    ## Параметры запроса:
    
    - **username**: Логин пользователя
      - Минимум 6 символов
      - Только буквы (a-z, A-Z), цифры (0-9) и подчеркивание (_)
      - Должен быть уникальным в системе
    
    - **password**: Пароль пользователя
      - Минимум 6 символов
      - Только буквы (a-z, A-Z), цифры (0-9) и подчеркивание (_)
    
    ## Ответ:
    
    - **id**: Уникальный идентификатор пользователя
    - **username**: Логин пользователя
    
    ## Коды ошибок:
    
    - **400**: Неверный формат логина/пароля или пользователь уже существует
      - "Логин должен содержать не менее 6 символов"
      - "Логин может содержать только буквы, цифры и символ подчеркивания"
      - "Пароль должен содержать не менее 6 символов"
      - "Пароль может содержать только буквы, цифры и символ подчеркивания"
      - "Username already registered"
    
    ## Пример запроса:
    
    ```json
    {
      "username": "john_doe",
      "password": "secure123"
    }
    ```
    
    ## Пример ответа:
    
    ```json
    {
      "id": 1,
      "username": "john_doe"
    }
    ```
    """
    
    if len(user.username) < 6:
        raise HTTPException(status_code=400, detail="Логин должен содержать не менее 6 символов")
    
    if not re.match("^[a-zA-Z0-9_]+$", user.username):
        raise HTTPException(status_code=400, detail="Логин может содержать только буквы, цифры и символ подчеркивания")
    
    if len(user.password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен содержать не менее 6 символов")
    
    if not re.match("^[a-zA-Z0-9_]+$", user.password):
        raise HTTPException(status_code=400, detail="Пароль может содержать только буквы, цифры и символ подчеркивания")

    db_user = repositories.UserRepository.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    try:
        auth.validate_password(user.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        created = repositories.UserRepository.create_user(db=db, user=user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    log_entry = schemas.LogCreate(action="register", details=f"User {user.username} registered")
    repositories.LogRepository.create_log(db, log_entry, created.id, user.username)
    
    return created

@app.post("/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    """
    Аутентификация пользователя и получение JWT токена.
    
    ## Описание:
    
    Проверяет учетные данные пользователя и выдает JWT токен для доступа к защищенным эндпоинтам.
    Токен действителен 60 минут и должен передаваться в заголовке Authorization.
    После успешного входа автоматически логирует действие в системе.
    
    ## Параметры запроса (форма данных):
    
    - **username**: Логин пользователя
    - **password**: Пароль пользователя
    
    ## Ответ:
    
    - **access_token**: JWT токен для аутентификации
    - **token_type**: Тип токена (всегда "bearer")
    
    ## Коды ошибок:
    
    - **401**: Неверный логин или пароль
      - "Incorrect username or password"
    
    ## Использование токена:
    
    Полученный токен необходимо использовать в заголовке Authorization:
    ```
    Authorization: Bearer <ваш_токен>
    ```
    
    ## Пример запроса:
    
    ```
    POST /auth/login
    Content-Type: application/x-www-form-urlencoded
    
    username=john_doe&password=secure123
    ```
    
    ## Пример ответа:
    
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer"
    }
    ```
    """
    user = repositories.UserRepository.get_user_by_username(db, form_data.username)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth.create_access_token(data={"sub": user.username})

    log_entry = schemas.LogCreate(action="login", details="User logged in")
    repositories.LogRepository.create_log(db, log_entry, user.id, user.username)

    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/analytics/log", response_model=schemas.LogResponse)
def log_action(
    log_data: schemas.LogCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Запись действия пользователя в лог.
    
    ## Описание:
    
    Записывает произвольное действие пользователя в систему логирования.
    Используется для отслеживания активности пользователей в системе.
    Требует аутентификации.
    
    ## Параметры запроса:
    
    - **action**: Тип действия (например: "play", "add_song", "login", "register")
    - **details**: Детали действия (опционально)
    
    ## Ответ:
    
    - **id**: Идентификатор записи лога
    - **username**: Имя пользователя
    - **action**: Тип действия
    - **details**: Детали действия (если были указаны)
    - **timestamp**: Время записи
    
    ## Коды ошибок:
    
    - **401**: Невалидный или отсутствующий токен
      - "Invalid token"
    
    ## Пример запроса:
    
    ```json
    {
      "action": "custom_action",
      "details": "Пользователь выполнил кастомное действие"
    }
    ```
    
    ## Пример ответа:
    
    ```json
    {
      "id": 123,
      "username": "john_doe",
      "action": "custom_action",
      "details": "Пользователь выполнил кастомное действие",
      "timestamp": "2024-01-15T14:30:00Z"
    }
    ```
    """
    return repositories.LogRepository.create_log(
        db=db,
        log=log_data,
        user_id=current_user.id,
        username=current_user.username
    )

@app.get("/analytics/stats", response_model=schemas.AnalyticsStats)
def get_stats(db: Session = Depends(database.get_db)):
    """
    Получение общей статистики по прослушиваниям.
    
    ## Описание:
    
    Возвращает агрегированную статистику по всем прослушиваниям песен в системе.
    Включает общее количество прослушиваний, самую и наименее популярную песню.
    Не требует аутентификации.
    
    ## Ответ:
    
    - **total_songs_played**: Общее количество прослушиваний
    - **most_played_song**: Название самой популярной песни
    - **least_played_song**: Название наименее популярной песни
    
    ## Пример ответа:
    
    ```json
    {
      "total_songs_played": 150,
      "most_played_song": "My Favorite Song - Artist",
      "least_played_song": "Unknown Track - Unknown Artist"
    }
    ```
    
    ## Примечание:
    
    Если песни не прослушивались, поля most_played_song и least_played_song могут быть null.
    """
    return repositories.LogRepository.get_analytics(db)

@app.get("/analytics/user", response_model=schemas.UserAnalytics)
def get_user_analytics(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Получение персональной аналитики пользователя.
    
    ## Описание:
    
    Возвращает детальную статистику активности текущего пользователя.
    Включает количество прослушиваний, избранных песен, сообщений в чате и другую информацию.
    Требует аутентификации.
    
    ## Ответ:
    
    - **username**: Имя пользователя
    - **total_plays**: Общее количество прослушиваний пользователя
    - **favorite_songs_count**: Количество песен в избранном (заполняется клиентом)
    - **global_songs_count**: Количество песен в общем плейлисте
    - **personal_songs_count**: Количество песен в личном плейлисте
    - **chat_messages_count**: Количество отправленных сообщений в чате
    - **most_played_song**: Самая прослушиваемая песня пользователя
    - **most_played_count**: Количество прослушиваний самой популярной песни
    
    ## Коды ошибок:
    
    - **401**: Невалидный или отсутствующий токен
      - "Invalid token"
    
    ## Пример ответа:
    
    ```json
    {
      "username": "john_doe",
      "total_plays": 42,
      "favorite_songs_count": 5,
      "global_songs_count": 150,
      "personal_songs_count": 10,
      "chat_messages_count": 23,
      "most_played_song": "My Favorite Song - Artist",
      "most_played_count": 15
    }
    ```
    """
    return repositories.AnalyticsRepository.get_user_analytics(db, current_user.id, current_user.username)

@app.post("/analytics/record-play")
def record_play(
    play_data: schemas.PlayHistoryCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Запись факта прослушивания песни.
    
    ## Описание:
    
    Регистрирует прослушивание песни пользователем.
    Увеличивает счетчик прослушиваний как в истории пользователя, так и в общей статистике песни.
    Автоматически логирует действие.
    Требует аутентификации.
    
    ## Параметры запроса:
    
    - **song_name**: Название песни
    - **song_type**: Тип песни ("global" или "personal")
    
    ## Ответ:
    
    - **message**: Статус операции
    - **play_count**: Текущее количество прослушиваний этой песни пользователем
    
    ## Коды ошибок:
    
    - **401**: Невалидный или отсутствующий токен
      - "Invalid token"
    
    ## Пример запроса:
    
    ```json
    {
      "song_name": "My Favorite Song.mp3",
      "song_type": "global"
    }
    ```
    
    ## Пример ответа:
    
    ```json
    {
      "message": "Play recorded",
      "play_count": 5
    }
    ```
    """
    
    play_record = repositories.PlayHistoryRepository.record_play(
        db, play_data, current_user.id, current_user.username
    )
    
    repositories.SongRepository.increment_play_count(
        db, play_data.song_name, play_data.song_type
    )
    
    log_entry = schemas.LogCreate(
        action="play",
        details=f"Played {play_data.song_name} ({play_data.song_type})"
    )
    repositories.LogRepository.create_log(db, log_entry, current_user.id, current_user.username)
    
    return {"message": "Play recorded", "play_count": play_record.play_count}

@app.post("/songs/add")
def add_song(
    song_data: schemas.SongCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Добавление новой песни в систему.
    
    ## Описание:
    
    Добавляет песню в базу данных системы.
    Если песня личная (song_type="personal"), связывается с текущим пользователем.
    Если песня общая (song_type="global"), доступна всем пользователям.
    Автоматически логирует действие.
    Требует аутентификации.
    
    ## Параметры запроса:
    
    - **name**: Отображаемое название песни
    - **filename**: Имя файла песни
    - **file_path**: Путь к файлу на сервере
    - **song_type**: Тип песни ("global" или "personal")
    
    ## Ответ:
    
    - **message**: Статус операции
    - **song_id**: Идентификатор созданной песни
    
    ## Коды ошибок:
    
    - **401**: Невалидный или отсутствующий токен
      - "Invalid token"
    
    ## Пример запроса:
    
    ```json
    {
      "name": "My Favorite Song",
      "filename": "my_favorite_song.mp3",
      "file_path": "/media/global/my_favorite_song.mp3",
      "song_type": "global"
    }
    ```
    
    ## Пример ответа:
    
    ```json
    {
      "message": "Song added",
      "song_id": 42
    }
    ```
    """
    song = repositories.SongRepository.create_song(
        db, song_data, current_user.id if song_data.song_type == 'personal' else None
    )
    
    log_entry = schemas.LogCreate(
        action="add_song",
        details=f"Added song {song_data.name} ({song_data.song_type})"
    )
    repositories.LogRepository.create_log(db, log_entry, current_user.id, current_user.username)
    
    return {"message": "Song added", "song_id": song.id}

@app.get("/songs/user", response_model=List[schemas.SongResponse])
def get_user_songs(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Получение списка песен пользователя.
    
    ## Описание:
    
    Возвращает список всех песен, доступных пользователю.
    Включает как общие песни (song_type="global"), так и личные песни пользователя (song_type="personal").
    Требует аутентификации.
    
    ## Ответ:
    
    Массив объектов SongResponse, каждый содержит:
    
    - **id**: Идентификатор песни
    - **name**: Название песни
    - **filename**: Имя файла
    - **file_path**: Путь к файлу
    - **song_type**: Тип песни ("global" или "personal")
    - **owner_id**: ID владельца (null для общих песен)
    - **upload_time**: Время загрузки
    - **play_count**: Количество прослушиваний
    
    ## Коды ошибок:
    
    - **401**: Невалидный или отсутствующий токен
      - "Invalid token"
    
    ## Пример ответа:
    
    ```json
    [
      {
        "id": 1,
        "name": "Global Song",
        "filename": "global_song.mp3",
        "file_path": "/media/global/global_song.mp3",
        "song_type": "global",
        "owner_id": null,
        "upload_time": "2024-01-15T10:30:00Z",
        "play_count": 150
      },
      {
        "id": 2,
        "name": "My Personal Song",
        "filename": "personal_song.mp3",
        "file_path": "/media/personal/john_doe/personal_song.mp3",
        "song_type": "personal",
        "owner_id": 1,
        "upload_time": "2024-01-15T11:00:00Z",
        "play_count": 5
      }
    ]
    ```
    """
    return repositories.SongRepository.get_songs_by_user(db, current_user.id)

@app.get("/chat/user-count")
def get_user_chat_count(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Получение количества сообщений пользователя в чате.
    
    ## Описание:
    
    Возвращает статистику по активности пользователя в чате.
    Показывает общее количество отправленных сообщений.
    Требует аутентификации.
    
    ## Ответ:
    
    - **username**: Имя пользователя
    - **chat_message_count**: Количество отправленных сообщений
    
    ## Коды ошибок:
    
    - **401**: Невалидный или отсутствующий токен
      - "Invalid token"
    
    ## Пример ответа:
    
    ```json
    {
      "username": "john_doe",
      "chat_message_count": 23
    }
    ```
    """
    count = repositories.ChatRepository.get_user_message_count(db, current_user.id)
    return {"username": current_user.username, "chat_message_count": count}

@app.websocket("/chat/{username}")
async def websocket_endpoint_path(websocket: WebSocket, username: str):
    """
    WebSocket эндпоинт для подключения к чату через путь.
    
    ## Описание:
    
    Устанавливает WebSocket соединение для участия в чате.
    При подключении пользователя отправляет уведомление всем участникам.
    Все сообщения пользователя транслируются всем подключенным клиентам.
    Сообщения сохраняются в базе данных.
    
    ## Параметры пути:
    
    - **username**: Имя пользователя для отображения в чате
    
    ## Пример использования:
    
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/chat/john_doe');
    
    ws.onmessage = (event) => {
      console.log('Получено сообщение:', event.data);
    };
    
    ws.send('Привет, чат!');
    ```
    """
    await _handle_websocket(websocket, username)

@app.websocket("/chat")
async def websocket_endpoint_query(websocket: WebSocket, username: Optional[str] = Query(None)):
    """
    WebSocket эндпоинт для подключения к чату через query-параметр.
    
    ## Описание:
    
    Альтернативный способ подключения к чату через query-параметр.
    Если username не указан, используется "Anonymous".
    
    ## Query-параметры:
    
    - **username**: Имя пользователя для отображения в чате (опционально)
    
    ## Пример использования:
    
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/chat?username=john_doe');
    
    ws.onmessage = (event) => {
      console.log('Получено сообщение:', event.data);
    };
    
    ws.send('Привет, чат!');
    ```
    """
    if not username:
        username = "Anonymous"
    await _handle_websocket(websocket, username)

async def _handle_websocket(websocket: WebSocket, username: str):
    """
    Обработчик WebSocket соединений для чата.
    
    ## Внутренняя логика:
    
    1. Устанавливает соединение и добавляет его в менеджер
    2. Отправляет приветственное сообщение о входе пользователя
    3. Принимает сообщения от пользователя и транслирует их всем участникам
    4. Сохраняет сообщения в базе данных (если пользователь зарегистрирован)
    5. Обрабатывает отключение пользователя
    
    Args:
        websocket (WebSocket): WebSocket соединение
        username (str): Имя пользователя
    """
    db_gen = database.get_db()
    db = None
    user_id = 0
    
    try:
        db = next(db_gen)
        user = repositories.UserRepository.get_user_by_username(db, username)
        if user:
            user_id = user.id
    except Exception:
        db = None
    finally:
        if db:
            try:
                next(db_gen)
            except StopIteration:
                pass

    await manager.connect(websocket)
    try:
        await manager.broadcast(f"System: {username} вошел в чат")

        while True:
            data = await websocket.receive_text()
            
            if not data or data.isspace():
                continue
                
            if db is not None:
                try:
                    repositories.ChatRepository.create_message(db, user_id=user_id, username=username, content=data)
                    db.commit()
                except Exception as e:
                    print(f"Ошибка сохранения сообщения: {e}")
                    try:
                        db.rollback()
                    except:
                        pass

            formatted_message = f"{username}: {data}"
            await manager.broadcast(formatted_message)

    except WebSocketDisconnect:
        await manager.broadcast(f"System: {username} вышел из чата")
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket ошибка: {e}")
        try:
            manager.disconnect(websocket)
        except:
            pass
    finally:
        try:
            if db:
                db.close()
        except:
            pass