from sqlalchemy import inspect

from app import app, db
from schema_sync import ensure_database_schema


def init_db():
    with app.app_context():
        ensure_database_schema()

        table_names = sorted(inspect(db.engine).get_table_names())
        print('Database initialized successfully.')
        print(f'Tables available: {", ".join(table_names)}')


if __name__ == '__main__':
    init_db()
