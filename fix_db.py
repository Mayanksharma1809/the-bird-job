from app import app, db
from sqlalchemy import text

def add_ats_score_column():
    with app.app_context():
        try:
            # Check if column exists (SQLite specific check)
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE portfolio_items ADD COLUMN ats_score INTEGER"))
                conn.commit()
                print("Column 'ats_score' added successfully to 'portfolio_items' table.")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("Column 'ats_score' already exists.")
            else:
                print(f"Error adding column: {e}")

if __name__ == "__main__":
    add_ats_score_column()
