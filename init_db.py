from sqlalchemy import inspect

from app import app, db, ensure_legacy_users_schema


def init_db():
    with app.app_context():
        db.create_all()
        ensure_legacy_users_schema()
        
        # New: Auto-add ats_score column if missing
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                # SQLite Specific Check - will fail silently/safe if column exists
                conn.execute(text("ALTER TABLE portfolio_items ADD COLUMN ats_score INTEGER"))
                conn.commit()
                print("Added missing 'ats_score' column to portfolio_items.")
        except Exception:
            pass # Already exists or other error

        table_names = sorted(inspect(db.engine).get_table_names())
        print('Database initialized successfully.')
        print(f'Tables available: {", ".join(table_names)}')


if __name__ == '__main__':
    init_db()
