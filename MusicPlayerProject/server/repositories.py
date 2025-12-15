from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_
from typing import Optional

from . import models, schemas, auth

class UserRepository:
    @staticmethod
    def get_user_by_username(db: Session, username: str):
        return db.query(models.User).filter(models.User.username == username).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int):
        return db.query(models.User).filter(models.User.id == user_id).first()

    @staticmethod
    def create_user(db: Session, user: schemas.UserCreate):
        auth.validate_password(user.password)

        hashed_password = auth.get_password_hash(user.password)
        db_user = models.User(username=user.username, hashed_password=hashed_password)

        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

class LogRepository:
    @staticmethod
    def create_log(db: Session, log: schemas.LogCreate, user_id: int, username: str):
        db_log = models.ActionLog(
            user_id=user_id,
            username=username,
            action=log.action,
            details=log.details
        )
        db.add(db_log)
        db.commit()
        db.refresh(db_log)
        return db_log

    @staticmethod
    def get_analytics(db: Session) -> schemas.AnalyticsStats:
        query = db.query(
            models.ActionLog.details,
            func.count(models.ActionLog.details).label("count")
        ).filter(
            models.ActionLog.action == "play"
        ).group_by(models.ActionLog.details)

        total_plays = db.query(models.ActionLog).filter(
            models.ActionLog.action == "play"
        ).count()

        most_played = query.order_by(desc("count")).first()
        least_played = query.order_by("count").first()

        return schemas.AnalyticsStats(
            total_songs_played=total_plays,
            most_played_song=most_played[0] if most_played else None,
            least_played_song=least_played[0] if least_played else None,
        )

class PlayHistoryRepository:
    @staticmethod
    def record_play(db: Session, play_data: schemas.PlayHistoryCreate, user_id: int, username: str):
        existing = db.query(models.PlayHistory).filter(
            models.PlayHistory.user_id == user_id,
            models.PlayHistory.song_name == play_data.song_name,
            models.PlayHistory.song_type == play_data.song_type
        ).first()
        
        if existing:
            existing.play_count += 1
            existing.last_played = func.now()
            db.commit()
            db.refresh(existing)
            return existing
        else:
            db_play = models.PlayHistory(
                user_id=user_id,
                username=username,
                song_name=play_data.song_name,
                song_type=play_data.song_type,
                play_count=1
            )
            db.add(db_play)
            db.commit()
            db.refresh(db_play)
            return db_play

    @staticmethod
    def get_user_play_history(db: Session, user_id: int, limit: int = 100):
        return (
            db.query(models.PlayHistory)
            .filter(models.PlayHistory.user_id == user_id)
            .order_by(models.PlayHistory.last_played.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_user_play_count(db: Session, user_id: int):
        result = db.query(
            func.sum(models.PlayHistory.play_count)
        ).filter(
            models.PlayHistory.user_id == user_id
        ).scalar()
        return result or 0

    @staticmethod
    def get_user_most_played(db: Session, user_id: int):
        result = (
            db.query(
                models.PlayHistory.song_name,
                func.sum(models.PlayHistory.play_count).label("total_plays")
            )
            .filter(models.PlayHistory.user_id == user_id)
            .group_by(models.PlayHistory.song_name)
            .order_by(desc("total_plays"))
            .first()
        )
        if result:
            return result[0], result[1]
        return None, 0

class SongRepository:
    @staticmethod
    def create_song(db: Session, song: schemas.SongCreate, user_id: Optional[int] = None):
        db_song = models.Song(
            name=song.name,
            filename=song.filename,
            file_path=song.file_path,
            song_type=song.song_type,
            owner_id=user_id
        )
        db.add(db_song)
        db.commit()
        db.refresh(db_song)
        return db_song

    @staticmethod
    def get_songs_by_user(db: Session, user_id: int, song_type: Optional[str] = None):
        query = db.query(models.Song).filter(
            or_(
                models.Song.owner_id == user_id,
                models.Song.song_type == 'global'
            )
        )
        
        if song_type:
            query = query.filter(models.Song.song_type == song_type)
            
        return query.all()

    @staticmethod
    def get_user_songs_count(db: Session, user_id: int, song_type: Optional[str] = None):
        query = db.query(models.Song).filter(models.Song.owner_id == user_id)
        
        if song_type:
            query = query.filter(models.Song.song_type == song_type)
            
        return query.count()

    @staticmethod
    def get_global_songs_count(db: Session):
        return db.query(models.Song).filter(models.Song.song_type == 'global').count()

    @staticmethod
    def increment_play_count(db: Session, filename: str, song_type: str):
        song = db.query(models.Song).filter(
            models.Song.filename == filename,
            models.Song.song_type == song_type
        ).first()
        
        if song:
            song.play_count += 1
            db.commit()
            db.refresh(song)
        return song

class ChatRepository:
    @staticmethod
    def create_message(db: Session, user_id: int, username: str, content: str):
        try:
            msg = models.ChatMessage(
                user_id=user_id,
               username=username,
                content=content
            )
            db.add(msg)
            db.commit()
            db.refresh(msg)
            return msg
        except Exception as e:
           db.rollback()
           raise e

    @staticmethod
    def get_last_messages(db: Session, limit: int = 50):
        return (
            db.query(models.ChatMessage)
            .order_by(models.ChatMessage.timestamp.asc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_user_message_count(db: Session, user_id: int):
        return db.query(models.ChatMessage).filter(
            models.ChatMessage.user_id == user_id
        ).count()

class AnalyticsRepository:
    @staticmethod
    def get_user_analytics(db: Session, user_id: int, username: str) -> schemas.UserAnalytics:
        
        play_count = PlayHistoryRepository.get_user_play_count(db, user_id)

        most_played_song, most_played_count = PlayHistoryRepository.get_user_most_played(db, user_id)
        
        chat_count = ChatRepository.get_user_message_count(db, user_id)
        
        global_count = SongRepository.get_global_songs_count(db)
        personal_count = SongRepository.get_user_songs_count(db, user_id, 'personal')
        
        
        return schemas.UserAnalytics(
            username=username,
            total_plays=play_count,
            favorite_songs_count=0,
            global_songs_count=global_count,
            personal_songs_count=personal_count,
            chat_messages_count=chat_count,
            most_played_song=most_played_song,
            most_played_count=most_played_count
        )