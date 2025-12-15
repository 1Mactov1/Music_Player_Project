from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    logs = relationship("ActionLog", back_populates="user", cascade="all, delete")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete")
    play_history = relationship("PlayHistory", back_populates="user", cascade="all, delete")
    songs = relationship("Song", back_populates="owner_user", cascade="all, delete")

class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    username = Column(String)
    action = Column(String)
    details = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="logs")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    username = Column(String)
    content = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="chat_messages")

class PlayHistory(Base):
    __tablename__ = "play_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    username = Column(String)
    song_name = Column(String)
    song_type = Column(String)
    play_count = Column(Integer, default=1)
    last_played = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="play_history")

class Song(Base):
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    filename = Column(String)
    file_path = Column(String)
    song_type = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    upload_time = Column(DateTime(timezone=True), server_default=func.now())
    play_count = Column(Integer, default=0)

    owner_user = relationship("User", back_populates="songs")