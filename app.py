from flask import Flask, render_template
from config.config import Config
from models import db
from routes import register_routes
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

    statements = []
    if 'auth_provider' not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN auth_provider VARCHAR(30) NULL")
    if 'google_sub' not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN google_sub VARCHAR(255) NULL")
    if 'full_name' not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN full_name VARCHAR(150) NULL")
    if 'created_at' not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN created_at DATETIME NULL")
    if 'updated_at' not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN updated_at DATETIME NULL")
    if 'last_login_at' not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN last_login_at DATETIME NULL")

    if not statements:
        return

    with db.engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        conn.execute(text("UPDATE users SET auth_provider = 'local' WHERE auth_provider IS NULL OR auth_provider = ''"))
        conn.execute(text(f"UPDATE users SET created_at = {now_expr} WHERE created_at IS NULL"))
        conn.execute(text(f"UPDATE users SET updated_at = {now_expr} WHERE updated_at IS NULL"))

    logger.info('Legacy users schema check complete. Added %s columns.', len(statements))

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404  # Assuming you have a 404.html

@app.errorhandler(500)
def internal_error(e):
    logger.error(f'Internal error: {e}')
    return render_template('500.html'), 500  # Assuming you have a 500.html

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        ensure_legacy_users_schema()
    app.run(debug=app.config['DEBUG'])
