import os
from pathlib import Path

basedir = Path(__file__).parent.absolute()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production-ratuwamai-2024'

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{basedir / "instance" / "database.sqlite"}'

    # Neon / Heroku sometimes give postgres:// — SQLAlchemy needs postgresql://
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Safe conversion (empty env var would crash int(''))
    _max = os.environ.get('MAX_CONTENT_LENGTH') or str(5 * 1024 * 1024)
    MAX_CONTENT_LENGTH = int(_max) if str(_max).isdigit() else 5 * 1024 * 1024

    UPLOAD_FOLDER = basedir / 'static' / 'uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    DELIVERY_CHARGE = 50  # NPR default
    # Average bike speed (km/h) used for approximate ETA
    AVG_DELIVERY_SPEED_KMH = float(os.environ.get('AVG_DELIVERY_SPEED_KMH', 18))
