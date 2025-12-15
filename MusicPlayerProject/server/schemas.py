from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True

class LogCreate(BaseModel):
    action: str
    details: Optional[str] = None

class LogResponse(LogCreate):
    id: int
    username: str
    timestamp: datetime

    class Config:
        from_attributes = True

class AnalyticsStats(BaseModel):
    total_songs_played: int
    most_played_song: Optional[str]
    least_played_song: Optional[str]

class PlayHistoryCreate(BaseModel):
    song_name: str
    song_type: str

class PlayHistoryResponse(PlayHistoryCreate):
    id: int
    username: str
    play_count: int
    last_played: datetime

    class Config:
        from_attributes = True

class SongCreate(BaseModel):
    name: str
    filename: str
    file_path: str
    song_type: str

class SongResponse(SongCreate):
    id: int
    owner_id: Optional[int]
    upload_time: datetime
    play_count: int

    class Config:
        from_attributes = True

class UserAnalytics(BaseModel):
    username: str
    total_plays: int
    favorite_songs_count: int
    global_songs_count: int
    personal_songs_count: int
    chat_messages_count: int
    most_played_song: Optional[str]
    most_played_count: Optional[int]

class ChatMessageCreate(BaseModel):
    content: str

class ChatMessageResponse(ChatMessageCreate):
    id: int
    username: str
    timestamp: datetime

    class Config:
        from_attributes = True