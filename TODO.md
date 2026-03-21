# The Bird Job - Render/Supabase Fix TODO

## Step 1: Verify Local Supabase (5 min)
- [ ] Copy Supabase Connection String: Dashboard > Settings > Connection String → `DATABASE_URL=postgresql://postgres.[pass]@db.[ref].supabase.co:5432/postgres`
- [ ] Append `?sslmode=require` if missing.
- [ ] Add to `.env` local.
- [ ] `python init_db.py` → Confirm tables created.

## Step 2: Render Environment Vars (5 min)
- [ ] Render Dashboard > Environment > Add `DATABASE_URL` (full Supabase string).
- [ ] Add `SECRET_KEY` (generate strong one).
- [ ] `PYTHON_VERSION=3.12`.

## Step 3: Render Deploy Config (3 min) ✅
- [x] Build Command: `pip install -r requirements.txt`
- [x] Start Command: `gunicorn app:app`
- [x] Procfile created.
- [x] config.py: Added pool_recycle/pool_timeout for Render.

## Step 4: Deploy & Test (5 min)
- [ ] Deploy → Check logs for DB connect.
- [ ] Visit site → Signup/Dashboard.
- [ ] If error, share Render logs.

## Next: ATS Backend (after deploy)

*Updated: {{ date }}*
