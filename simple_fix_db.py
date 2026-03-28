import sqlite3
import os

db_path = r'c:\Users\lenovo\OneDrive\Desktop\THEbirdJOB\instance\job_portal.db'

def fix():
    if not os.path.exists(db_path):
        print(f"DB not found at {db_path}")
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE portfolio_items ADD COLUMN ats_score INTEGER")
        conn.commit()
        conn.close()
        print("Success")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix()
