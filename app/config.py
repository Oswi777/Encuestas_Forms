import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-change-me')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

    SHIFTS = ['T1', 'T2', 'T3', 'MIXTO', '4X3']

    DEFAULT_LANGUAGE = os.getenv('DEFAULT_LANGUAGE', 'es')
    APP_TITLE = os.getenv('APP_TITLE', 'Saltillo')

    TIME_ZONE = os.getenv('TIME_ZONE', 'America/Mexico_City')

    DATABASE_URL = os.getenv('DATABASE_URL')
    if DATABASE_URL:
        # Render provides postgres://; SQLAlchemy expects postgresql+psycopg2://
        SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace('postgres://', 'postgresql+psycopg2://', 1)
    else:
        db_path = BASE_DIR / 'instance' / 'app.db'
        db_path.parent.mkdir(parents=True, exist_ok=True)
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path.as_posix()}'
