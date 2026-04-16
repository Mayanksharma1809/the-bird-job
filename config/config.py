import os
import logging
from datetime import timedelta
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

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

    _local_database_url = normalize_database_url(os.environ.get('LOCAL_DATABASE_URL'))
    _database_url = normalize_database_url(
        os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DB_URL')
    )
    if _local_database_url:
        _database_url = _local_database_url
    if has_placeholder_in_url(_database_url):
        _database_url = None

    _college_database_url = normalize_database_url(os.environ.get('COLLEGE_DATABASE_URL'))
    if has_placeholder_in_url(_college_database_url):
        _college_database_url = None

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

    if not _database_url:
        logger.warning(
            'No external database URL configured; falling back to local SQLite. '
            'Set DATABASE_URL or SUPABASE_DB_URL for production deployments.'
        )

    SQLALCHEMY_DATABASE_URI = _database_url or 'sqlite:///job_portal.db'
    
    # Second Database for Skill Tests
    _skill_db_url = normalize_database_url(os.environ.get('SKILL_TEST_DATABASE_URL'))
    # Always define the bind key so SQLAlchemy doesn't crash if the env var is missing
    SQLALCHEMY_BINDS = {
        'skill_test': _local_database_url or _skill_db_url or SQLALCHEMY_DATABASE_URI,
        'college': _college_database_url or 'sqlite:///college_portal.db',
    }
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 30,
        'echo': os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes'),
    }
    DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    # Public branding/SEO configuration
    SITE_NAME = os.environ.get('SITE_NAME', 'The Bird Job')
    SITE_DESCRIPTION = os.environ.get(
        'SITE_DESCRIPTION',
        'The Bird Job helps candidates find jobs and employers hire faster.',
    )
    SITE_URL = (os.environ.get('SITE_URL') or '').strip()
    SITE_LOGO_PATH = os.environ.get('SITE_LOGO_PATH', '/static/brand/logo-512.png')
    SITE_FAVICON_PATH = os.environ.get('SITE_FAVICON_PATH', '/static/brand/favicon-48.png')
    SITE_APPLE_TOUCH_ICON_PATH = os.environ.get(
        'SITE_APPLE_TOUCH_ICON_PATH',
        '/static/brand/apple-touch-icon-180.png',
    )
    
    # Job API Configuration
    JOBS_API_URL = os.environ.get('JOBS_API_URL', 'https://remotive.com/api/remote-jobs')
    JOBS_API_URL_2 = os.environ.get('JOBS_API_URL_2')
    JOBS_API_URLS = parse_csv(os.environ.get('JOBS_API_URLS'))
    JOBS_API_TIMEOUT = parse_int(os.environ.get('JOBS_API_TIMEOUT'), 10)
    CANDIDATE_DASHBOARD_JOB_LIMIT = parse_int(os.environ.get('CANDIDATE_DASHBOARD_JOB_LIMIT'), 12)
    
    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI')
    GOOGLE_DISCOVERY_URL = 'https://accounts.google.com/.well-known/openid-configuration'
    GOOGLE_ANALYTICS_ID = os.environ.get('GOOGLE_ANALYTICS_ID', 'G-0YN3L0KL64')
    
    # ===== AI/ML APIs =====
    # Gemini API (Google)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    
    # Groq API
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    GROQ_MODEL = 'mixtral-8x7b-32768'  # Default Groq model
    
    # Ollama (Local LLM)
    OLLAMA_API_URL = os.environ.get('OLLAMA_API_URL', 'http://localhost:11434')
    OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama2')
    
    # ===== ATS SERVICE =====
    ATS_API_KEY = os.environ.get('ATS_API_KEY')
    ATS_API_URL = os.environ.get('ATS_API_URL')
