# Job Portal App

A Flask-based job portal application.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Create a local MySQL database:
   ```
   CREATE DATABASE the_bird_job;
   ```

3. Configure environment variables in `.env`:
   ```
   SECRET_KEY=your-secret-key
   DEBUG=True

   # Preferred explicit DB URL
   DATABASE_URL=mysql+pymysql://root:yourpassword@127.0.0.1:3306/the_bird_job

   # OR use split MySQL vars instead of DATABASE_URL
   # MYSQL_USER=root
   # MYSQL_PASSWORD=yourpassword
   # MYSQL_HOST=127.0.0.1
   # MYSQL_PORT=3306
   # MYSQL_DB=the_bird_job

   GOOGLE_CLIENT_ID=your-google-client-id
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   GOOGLE_REDIRECT_URI=http://127.0.0.1:5000/auth/google/callback
   ```

4. Run the app:
   ```
   python app.py
   ```
   On first run, SQLAlchemy will create tables:
   - `users`
   - `candidate_profiles`
   - `employer_profiles`
   - `login_events`

## Configuration

Secrets and API keys are stored in the `config/` folder. Use environment variables for sensitive data.

## Structure

- `app.py`: Main application file
- `config/`: Configuration and secrets
- `templates/`: HTML templates
- `models.py`: SQLAlchemy models for users/profiles/login history
"# thebirdjob" 
