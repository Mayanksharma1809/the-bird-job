import html
import json
from urllib.parse import urljoin

from flask import Flask, render_template, request, send_from_directory
from config.config import Config
from models import db
from routes import register_routes
from ats_routes import ats_bp
import logging
import os
from sqlalchemy import inspect, text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Register routes
register_routes(app)
app.register_blueprint(ats_bp)


def build_google_analytics_tag(measurement_id):
    if not measurement_id:
        return ''
    return f"""
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}"></script>
    <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', '{measurement_id}');
    </script>
    """.strip()


def resolve_public_site_url():
    configured_url = (app.config.get('SITE_URL') or '').strip()
    if configured_url:
        return configured_url.rstrip('/')
    return request.url_root.rstrip('/')


def build_absolute_public_url(path_or_url):
    raw_value = (path_or_url or '').strip()
    if raw_value.startswith('http://') or raw_value.startswith('https://'):
        return raw_value
    return urljoin(f"{resolve_public_site_url()}/", raw_value.lstrip('/'))


def build_site_branding_tag():
    site_name = (app.config.get('SITE_NAME') or 'The Bird Job').strip()
    site_description = (
        app.config.get('SITE_DESCRIPTION')
        or 'The Bird Job helps candidates find jobs and employers hire faster.'
    ).strip()

    favicon_url = build_absolute_public_url(app.config.get('SITE_FAVICON_PATH', '/static/brand/favicon-48.png'))
    favicon_svg_url = build_absolute_public_url('/static/brand/favicon.svg')
    apple_touch_icon_url = build_absolute_public_url(
        app.config.get('SITE_APPLE_TOUCH_ICON_PATH', '/static/brand/apple-touch-icon-180.png')
    )
    logo_url = build_absolute_public_url(app.config.get('SITE_LOGO_PATH', '/static/brand/logo-512.png'))
    canonical_url = request.base_url

    organization_schema = {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        'name': site_name,
        'url': resolve_public_site_url(),
        'logo': logo_url,
    }
    website_schema = {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': site_name,
        'url': resolve_public_site_url(),
    }

    escaped_site_name = html.escape(site_name)
    escaped_site_description = html.escape(site_description)

    return f"""
<meta data-site-branding-seo="1" name="application-name" content="{escaped_site_name}">
<link rel="canonical" href="{html.escape(canonical_url)}">
<link rel="icon" href="{html.escape(favicon_url)}" type="image/png" sizes="48x48">
<link rel="alternate icon" href="{html.escape(favicon_svg_url)}" type="image/svg+xml">
<link rel="apple-touch-icon" href="{html.escape(apple_touch_icon_url)}" sizes="180x180">
<meta property="og:site_name" content="{escaped_site_name}">
<meta property="og:type" content="website">
<meta property="og:url" content="{html.escape(canonical_url)}">
<meta property="og:title" content="{escaped_site_name}">
<meta property="og:description" content="{escaped_site_description}">
<meta property="og:image" content="{html.escape(logo_url)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{escaped_site_name}">
<meta name="twitter:description" content="{escaped_site_description}">
<meta name="twitter:image" content="{html.escape(logo_url)}">
<script type="application/ld+json">{json.dumps(organization_schema, ensure_ascii=False, separators=(',', ':'))}</script>
<script type="application/ld+json">{json.dumps(website_schema, ensure_ascii=False, separators=(',', ':'))}</script>
""".strip()


@app.after_request
def inject_google_analytics(response):
    content_type = (response.content_type or '').lower()
    if 'text/html' not in content_type:
        return response

    body = response.get_data(as_text=True)
    if '</head>' not in body:
        return response

    injections = []
    measurement_id = app.config.get('GOOGLE_ANALYTICS_ID')
    if measurement_id and 'googletagmanager.com/gtag/js' not in body:
        injections.append(build_google_analytics_tag(measurement_id))

    if 'data-site-branding-seo="1"' not in body:
        injections.append(build_site_branding_tag())

    if not injections:
        return response

    head_injection = '\n    '.join(injections)
    response.set_data(body.replace('</head>', f'    {head_injection}\n</head>', 1))
    return response


def ensure_legacy_users_schema():
    """
    Adds newly introduced columns for legacy databases that already had a users table.
    This prevents 500 errors caused by missing columns after model updates.
    """
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()
    if 'users' not in table_names:
        return

    existing_columns = {col['name'] for col in inspector.get_columns('users')}
    dialect = db.engine.dialect.name
    now_expr = 'NOW()' if dialect == 'mysql' else 'CURRENT_TIMESTAMP'
    datetime_type = 'TIMESTAMP' if dialect == 'postgresql' else 'DATETIME'

    statements = []
    if 'auth_provider' not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN auth_provider VARCHAR(30) NULL")
    if 'google_sub' not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN google_sub VARCHAR(255) NULL")
    if 'full_name' not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN full_name VARCHAR(150) NULL")
    if 'created_at' not in existing_columns:
        statements.append(f"ALTER TABLE users ADD COLUMN created_at {datetime_type} NULL")
    if 'updated_at' not in existing_columns:
        statements.append(f"ALTER TABLE users ADD COLUMN updated_at {datetime_type} NULL")
    if 'last_login_at' not in existing_columns:
        statements.append(f"ALTER TABLE users ADD COLUMN last_login_at {datetime_type} NULL")

    if not statements:
        return

    with db.engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        conn.execute(text("UPDATE users SET auth_provider = 'local' WHERE auth_provider IS NULL OR auth_provider = ''"))
        conn.execute(text(f"UPDATE users SET created_at = {now_expr} WHERE created_at IS NULL"))
        conn.execute(text(f"UPDATE users SET updated_at = {now_expr} WHERE updated_at IS NULL"))

    logger.info('Legacy users schema check complete. Added %s columns.', len(statements))


def ensure_legacy_employer_profiles_schema():
    """
    Adds newly introduced columns for legacy employer_profiles tables.
    """
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()
    if 'employer_profiles' not in table_names:
        return

    existing_columns = {col['name'] for col in inspector.get_columns('employer_profiles')}
    statements = []

    if 'plan_tier' not in existing_columns:
        statements.append("ALTER TABLE employer_profiles ADD COLUMN plan_tier VARCHAR(30) NULL")

    if not statements:
        return

    with db.engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        conn.execute(
            text("UPDATE employer_profiles SET plan_tier = 'starter' WHERE plan_tier IS NULL OR plan_tier = ''")
        )

    logger.info('Legacy employer_profiles schema check complete. Added %s columns.', len(statements))

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404  # Assuming you have a 404.html

@app.errorhandler(500)
def internal_error(e):
    logger.error(f'Internal error: {e}')
    return render_template('500.html'), 500  # Assuming you have a 500.html

# Yeh __main__ ke BAHAR rakho
with app.app_context():
    db.create_all()
    ensure_legacy_users_schema()
    ensure_legacy_employer_profiles_schema()


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'brand'),
        'favicon-48.png',
        mimetype='image/png',
    )


if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])
