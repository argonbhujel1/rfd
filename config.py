import os
from pathlib import Path

basedir = Path(__file__).parent.absolute()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production-ratuwamai-2024'
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{basedir / "instance" / "database.sqlite"}'
    
    # Neon को postgres:// लाई postgresql:// मा बदल्नुहोस्
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Safe conversion (empty string आउँदा default प्रयोग गर्छ)
    _max = os.environ.get('MAX_CONTENT_LENGTH') or str(5 * 1024 * 1024)
    MAX_CONTENT_LENGTH = int(_max) if _max.isdigit() else 5 * 1024 * 1024
    
    UPLOAD_FOLDER = basedir / 'static' / 'uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    DELIVERY_CHARGE = 50