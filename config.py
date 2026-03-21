import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "sslmode": "require"
        },
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    DEBUG = os.environ.get('DEBUG', 'False') == 'True'