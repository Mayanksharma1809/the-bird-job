import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

PLACEHOLDER_VALUES = {
    'your_mysql_password',
    'yourpassword',
    'change_me',
    'changeme',
}


def has_placeholder(value):
    lowered = (value or '').strip().lower()
    if not lowered:
        return False
    return lowered in PLACEHOLDER_VALUES


def has_placeholder_in_url(value):
    lowered = (value or '').strip().lower()
    if not lowered:
        return False
    return any(token in lowered for token in PLACEHOLDER_VALUES)


class Config:
    SECRET_KEY = (
        os.environ.get('SECRET_KEY')
        or os.environ.get('FLASK_SECRET_KEY')
        or 'fallback-secret-key'
    )

    _database_url = os.environ.get('DATABASE_URL')
    if has_placeholder_in_url(_database_url):
        _database_url = None

    if not _database_url:
        mysql_user = os.environ.get('MYSQL_USER')
        mysql_password = os.environ.get('MYSQL_PASSWORD')
        mysql_host = os.environ.get('MYSQL_HOST', '127.0.0.1')
        mysql_port = os.environ.get('MYSQL_PORT', '3306')
        mysql_db = os.environ.get('MYSQL_DB')
        if has_placeholder(mysql_password):
            mysql_password = None
        if mysql_user and mysql_password is not None and mysql_db:
            _database_url = (
                f"mysql+pymysql://{quote_plus(mysql_user)}:{quote_plus(mysql_password)}"
                f"@{mysql_host}:{mysql_port}/{mysql_db}"
            )

    SQLALCHEMY_DATABASE_URI = _database_url or 'sqlite:///job_portal.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI')
    GOOGLE_DISCOVERY_URL = 'https://accounts.google.com/.well-known/openid-configuration'
    # Add other API keys or secrets here
    # API_KEY = os.environ.get('API_KEY')
    # etc.
