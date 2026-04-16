import logging
from datetime import datetime

from sqlalchemy import inspect, text

from models import (
    CandidateJobAction,
    CandidateProfile,
    CollegeAdmin,
    CollegeStudent,
    EmployerJob,
    EmployerProfile,
    LoginEvent,
    Message,
    PortfolioItem,
    User,
    db,
)

logger = logging.getLogger(__name__)

MODEL_CLASSES = (
    User,
    CandidateProfile,
    EmployerProfile,
    EmployerJob,
    CandidateJobAction,
    LoginEvent,
    Message,
    PortfolioItem,
    CollegeAdmin,
    CollegeStudent,
)

# Values used to backfill columns that were added after rows already existed.
BACKFILL_RULES = {
    ('users', 'auth_provider'): ('local', True),
    ('users', 'created_at'): (datetime.utcnow, False),
    ('users', 'updated_at'): (datetime.utcnow, False),
    ('users', 'last_login_at'): (None, False),
    ('employer_profiles', 'plan_tier'): ('starter', True),
    ('employer_profiles', 'created_at'): (datetime.utcnow, False),
    ('employer_profiles', 'updated_at'): (datetime.utcnow, False),
    ('employer_jobs', 'status'): ('active', True),
    ('employer_jobs', 'created_at'): (datetime.utcnow, False),
    ('employer_jobs', 'updated_at'): (datetime.utcnow, False),
    ('candidate_job_actions', 'source'): ('api', True),
    ('candidate_job_actions', 'action'): ('applied', True),
    ('candidate_job_actions', 'status'): ('submitted', True),
    ('candidate_job_actions', 'created_at'): (datetime.utcnow, False),
    ('candidate_job_actions', 'updated_at'): (datetime.utcnow, False),
    ('login_events', 'is_new_user'): (False, False),
    ('login_events', 'created_at'): (datetime.utcnow, False),
    ('messages', 'is_read'): (False, False),
    ('portfolio_items', 'created_at'): (datetime.utcnow, False),
    ('college_admins', 'role'): ('admin', True),
    ('college_admins', 'auth_provider'): ('local', True),
    ('college_admins', 'created_at'): (datetime.utcnow, False),
    ('college_admins', 'updated_at'): (datetime.utcnow, False),
    ('college_students', 'role'): ('student', True),
    ('college_students', 'auth_provider'): ('local', True),
    ('college_students', 'created_at'): (datetime.utcnow, False),
    ('college_students', 'updated_at'): (datetime.utcnow, False),
}


def _get_engine_for_model(model):
    bind_key = getattr(model, '__bind_key__', None)
    if bind_key:
        return db.engines[bind_key]
    return db.engine


def _quote_identifier(engine, identifier):
    return engine.dialect.identifier_preparer.quote(identifier)


def _build_add_column_sql(engine, table_name, column_name, column_type):
    quoted_table = _quote_identifier(engine, table_name)
    quoted_column = _quote_identifier(engine, column_name)
    compiled_type = column_type.compile(dialect=engine.dialect)
    # Add new columns as nullable so legacy rows never break on deploy.
    return f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {compiled_type} NULL"


def _backfill_column(engine, table_name, column_name, value, treat_empty_string_as_missing=False):
    if value is None:
        return

    quoted_table = _quote_identifier(engine, table_name)
    quoted_column = _quote_identifier(engine, column_name)

    if treat_empty_string_as_missing:
        sql = (
            f"UPDATE {quoted_table} "
            f"SET {quoted_column} = :value "
            f"WHERE {quoted_column} IS NULL OR {quoted_column} = ''"
        )
    else:
        sql = f"UPDATE {quoted_table} SET {quoted_column} = :value WHERE {quoted_column} IS NULL"

    with engine.begin() as conn:
        conn.execute(text(sql), {'value': value() if callable(value) else value})


def ensure_model_schema(model):
    """
    Add any missing columns for a model table without disturbing existing rows.

    This is intentionally conservative: it only adds columns and backfills known
    defaults. It does not try to alter constraints or drop anything.
    """
    engine = _get_engine_for_model(model)
    table = model.__table__
    inspector = inspect(engine)

    if table.name not in inspector.get_table_names():
        return 0

    existing_columns = {column['name'] for column in inspector.get_columns(table.name)}
    added_columns = 0

    for column in table.columns:
        if column.name in existing_columns:
            continue

        add_sql = _build_add_column_sql(engine, table.name, column.name, column.type)
        with engine.begin() as conn:
            conn.execute(text(add_sql))

        added_columns += 1
        logger.info('Added missing column %s.%s', table.name, column.name)

        backfill_rule = BACKFILL_RULES.get((table.name, column.name))
        if backfill_rule:
            value, treat_empty_string_as_missing = backfill_rule
            _backfill_column(
                engine,
                table.name,
                column.name,
                value,
                treat_empty_string_as_missing=treat_empty_string_as_missing,
            )

    return added_columns


def ensure_database_schema():
    """
    Create any missing tables and backfill missing columns for all app models.
    """
    db.create_all()

    total_added = 0
    for model in MODEL_CLASSES:
        try:
            total_added += ensure_model_schema(model)
        except Exception:
            logger.exception('Failed to sync schema for table %s', model.__tablename__)
            raise

    if total_added:
        logger.info('Database schema sync complete. Added %s missing columns.', total_added)
    else:
        logger.info('Database schema sync complete. No missing columns detected.')

