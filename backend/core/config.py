from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "MBA — Multimodal Behavioral Analytics"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "https://mba.vercel.app"]

    # Database
    DATABASE_URL: Optional[str] = None
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None

    # Whisper
    WHISPER_MODEL: str = "base"          # tiny | base | small | medium
    WHISPER_DEVICE: str = "cpu"

    # MediaPipe
    FACE_DETECTION_CONFIDENCE: float = 0.7
    FACE_TRACKING_CONFIDENCE: float = 0.5

    # Audio
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHUNK_DURATION: float = 0.5    # seconds per analysis chunk

    # Analytics
    WINDOW_SIZE_SECONDS: float = 3.0     # temporal fusion window
    ANALYTICS_FPS: int = 10             # analytics updates per second

    # Dataset
    DATASET_DIR: str = "data"
    DATASET_AUTO_SAVE: bool = True
    EMBEDDING_DEVICE: str = "cpu"

    # Training
    DEBERTA_MODEL: str = "microsoft/deberta-v3-base"
    TRAINING_OUTPUT_DIR: str = "models"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
