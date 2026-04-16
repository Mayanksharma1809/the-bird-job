# Job Portal App

A Flask-based job portal application.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Configure environment variables in `.env`:
   ```
   SECRET_KEY=your-secret-key
   DEBUG=True

   # Local development uses SQLite by default
   LOCAL_DATABASE_URL=sqlite:///job_portal.db
   COLLEGE_DATABASE_URL=sqlite:///college_portal.db

   # Recommended for deployed app (Supabase Postgres)
   # Copy from Supabase > Project Settings > Database > Connection string
   DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?sslmode=require
   # (Optional alias supported by this app)
   # SUPABASE_DB_URL=postgresql://...

   # Jobs API for candidate dashboard feed (optional override)
   # Default already points to Remotive API
   # JOBS_API_URL=https://remotive.com/api/remote-jobs
   # JOBS_API_URL_2=https://second-provider.com/api/jobs
   # JOBS_API_URLS=https://third-provider.com/jobs,https://fourth-provider.com/jobs
   # JOBS_API_TIMEOUT=10
   # CANDIDATE_DASHBOARD_JOB_LIMIT=12

   # OR local MySQL fallback (if DATABASE_URL is not set)
   # MYSQL_USER=root
   # MYSQL_PASSWORD=yourpassword
   # MYSQL_HOST=127.0.0.1
   # MYSQL_PORT=3306
   # MYSQL_DB=the_bird_job

   GOOGLE_CLIENT_ID=your-google-client-id
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   GOOGLE_REDIRECT_URI=http://127.0.0.1:5000/auth/google/callback
   ```

3. Run the app:
   ```
   python app.py
   ```
   For production/Supabase, create tables once with:
   ```
   python init_db.py
   ```

   SQLAlchemy will create tables:
   - `users`
   - `candidate_profiles`
   - `employer_profiles`
   - `login_events`
   - `employer_jobs`
   - `candidate_job_actions`

   College portal tables live in the college database and are split by user type:
   - `college_admins`
   - `college_students`

   College routes:
   - `/college/login`
   - `/college/admin/login`
   - `/college/student/login`
   - `/college/admin/signup`
   - `/college/student/signup`

## Render Deployment (Free Tier)

1. Connect GitHub repo to Render.com (Web Service).
2. **Environment Vars**:
   ```
   DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?sslmode=require
   SECRET_KEY=sk-very-long-random-secret-key-generate-one
   ```
3. **Settings**:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app`
   - Plan: Free
4. Deploy → Check logs for DB connect. Run `python init_db.py` manually if tables missing.

See TODO.md for step-by-step.

## Configuration

Secrets and API keys are stored in the `config/` folder. Use environment variables for sensitive data.

## Structure

- `app.py`: Main application file
- `config/`: Configuration and secrets
- `templates/`: HTML templates
- `models.py`: SQLAlchemy models for users/profiles/login history
"# thebirdjob" 
