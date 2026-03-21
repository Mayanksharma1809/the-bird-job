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


def normalize_database_url(value):
    cleaned = (value or '').strip()
    if cleaned.startswith('postgres://'):
        # SQLAlchemy expects "postgresql://".
        cleaned = cleaned.replace('postgres://', 'postgresql://', 1)
    # Ensure SSL mode is set for PostgreSQL connections
    if cleaned.startswith('postgresql://') and 'sslmode=' not in cleaned:
        separator = '&' if '?' in cleaned else '?'
        cleaned += f'{separator}sslmode=require'
    return cleaned


def parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_csv(value):
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


class Config:
    SECRET_KEY = (
        os.environ.get('SECRET_KEY')
        or os.environ.get('FLASK_SECRET_KEY')
        or 'fallback-secret-key'
    )

    _database_url = normalize_database_url(
        os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DB_URL')
    )
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
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 30,
        'echo': os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes'),
    }
    DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
    JOBS_API_URL = os.environ.get('JOBS_API_URL', 'https://remotive.com/api/remote-jobs')
    JOBS_API_URL_2 = os.environ.get('JOBS_API_URL_2')
    JOBS_API_URLS = parse_csv(os.environ.get('JOBS_API_URLS'))
    JOBS_API_TIMEOUT = parse_int(os.environ.get('JOBS_API_TIMEOUT'), 10)
    CANDIDATE_DASHBOARD_JOB_LIMIT = parse_int(os.environ.get('CANDIDATE_DASHBOARD_JOB_LIMIT'), 12)
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI')
    GOOGLE_DISCOVERY_URL = 'https://accounts.google.com/.well-known/openid-configuration'
    # Add other API keys or secrets here
    # API_KEY = os.environ.get('API_KEY')
    # etc.
