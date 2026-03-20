import json
import re
import secrets
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import flash, redirect, render_template, request, session, url_for

from candidate_dashboard_routes import register_candidate_dashboard_routes
from employer_dashboard_routes import register_employer_dashboard_routes
from models import CandidateProfile, EmployerProfile, LoginEvent, User, db


def register_routes(app):
    def normalize_role(raw_role):
        value = (raw_role or '').strip().lower()
        if value in ('candidate', 'jobseeker', 'job_seeker', 'seeker'):
            return 'candidate'
        if value in ('employer', 'recruiter', 'company'):
            return 'employer'
        return 'candidate'

    def dashboard_endpoint_for_role(role):
        return 'candidate_dashboard' if normalize_role(role) == 'candidate' else 'employer_dashboard'

    def profile_form_endpoint_for_role(role):
        return 'candidate_form' if normalize_role(role) == 'candidate' else 'employer_form'

    def build_unique_username(source):
        base = re.sub(r'[^a-zA-Z0-9_]+', '_', (source or '').strip().lower()).strip('_')
        if not base:
            base = 'user'
        base = base[:150]

        candidate = base
        suffix = 1
        while User.query.filter_by(username=candidate).first():
            suffix_text = f'_{suffix}'
            candidate = f'{base[:150 - len(suffix_text)]}{suffix_text}'
            suffix += 1
        return candidate

    def fetch_json(url, headers=None):
        request_obj = Request(url, headers=headers or {})
        with urlopen(request_obj, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))

    def post_form_json(url, data):
        encoded = urlencode(data).encode('utf-8')
        request_obj = Request(url, data=encoded, method='POST')
        request_obj.add_header('Content-Type', 'application/x-www-form-urlencoded')
        with urlopen(request_obj, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))

    def google_redirect_uri():
        return app.config.get('GOOGLE_REDIRECT_URI') or url_for('google_callback', _external=True)

    def get_logged_in_user():
        user_id = session.get('user_id')
        if not user_id:
            return None
        return db.session.get(User, user_id)

    def has_completed_profile(user):
        role = normalize_role(user.role)
        if role == 'candidate':
            return CandidateProfile.query.filter_by(user_id=user.id).first() is not None
        return EmployerProfile.query.filter_by(user_id=user.id).first() is not None

    def has_candidate_profile(user):
        return CandidateProfile.query.filter_by(user_id=user.id).first() is not None

    def has_employer_profile(user):
        return EmployerProfile.query.filter_by(user_id=user.id).first() is not None

    def resolve_role_for_existing_google_user(user, selected_role):
        selected = normalize_role(selected_role)
        candidate_done = has_candidate_profile(user)
        employer_done = has_employer_profile(user)

        if candidate_done and not employer_done:
            return 'candidate'
        if employer_done and not candidate_done:
            return 'employer'
        return selected

    def next_step_endpoint_for_user(user):
        if has_completed_profile(user):
            return dashboard_endpoint_for_role(user.role)
        return profile_form_endpoint_for_role(user.role)

    def first_non_empty(values, fallback=''):
        for value in values:
            cleaned = (value or '').strip()
            if cleaned:
                return cleaned
        return fallback

    def build_initials(value):
        parts = [part for part in (value or '').split() if part]
        if not parts:
            return 'U'
        if len(parts) == 1:
            return parts[0][:2].upper()
        return f'{parts[0][0]}{parts[-1][0]}'.upper()

    def candidate_dashboard_user(user):
        profile = CandidateProfile.query.filter_by(user_id=user.id).first()
        name = first_non_empty(
            [
                profile.name if profile else '',
                user.full_name,
                user.username,
            ],
            fallback='Candidate',
        )
        email = first_non_empty(
            [
                profile.email if profile else '',
                user.email,
            ]
        )
        return {
            'name': name,
            'email': email,
            'initials': build_initials(name),
        }

    def employer_dashboard_user(user):
        profile = EmployerProfile.query.filter_by(user_id=user.id).first()
        company_name = first_non_empty(
            [
                profile.company_name if profile else '',
                user.full_name,
                user.username,
            ],
            fallback='Employer',
        )
        company_size = first_non_empty(
            [
                profile.company_size if profile else '',
            ]
        )
        email = first_non_empty(
            [
                profile.email if profile else '',
                user.email,
            ]
        )
        return {
            'company_name': company_name,
            'company_size': company_size,
            'email': email,
            'initials': build_initials(company_name),
        }

    def create_local_user(role, email, password, username='', full_name=''):
        clean_role = normalize_role(role)
        clean_email = (email or '').strip().lower()
        clean_password = password or ''
        clean_username = (username or '').strip()
        clean_full_name = (full_name or '').strip()

        if not clean_email or not clean_password:
            return None, 'Email and password are required.'

        if User.query.filter_by(email=clean_email).first():
            return None, 'Email already exists'

        if not clean_username:
            username_source = clean_full_name or clean_email.split('@')[0] or 'user'
            clean_username = build_unique_username(username_source)
        elif User.query.filter_by(username=clean_username).first():
            clean_username = build_unique_username(clean_username)

        new_user = User(
            username=clean_username,
            email=clean_email,
            password=clean_password,
            role=clean_role,
            auth_provider='local',
            full_name=clean_full_name or clean_username,
        )
        db.session.add(new_user)
        db.session.flush()
        return new_user, None

    def record_login_event(user, provider, is_new_user=False):
        forwarded_for = request.headers.get('X-Forwarded-For', '')
        ip_address = forwarded_for.split(',')[0].strip() if forwarded_for else request.remote_addr
        event = LoginEvent(
            user_id=user.id,
            provider=provider,
            role_snapshot=normalize_role(user.role),
            is_new_user=is_new_user,
            ip_address=ip_address,
            user_agent=(request.user_agent.string or '')[:512],
        )
        user.last_login_at = datetime.utcnow()
        db.session.add(event)

    dashboard_helpers = {
        'candidate_dashboard_user': candidate_dashboard_user,
        'dashboard_endpoint_for_role': dashboard_endpoint_for_role,
        'employer_dashboard_user': employer_dashboard_user,
        'first_non_empty': first_non_empty,
        'get_logged_in_user': get_logged_in_user,
        'has_completed_profile': has_completed_profile,
        'normalize_role': normalize_role,
    }
    register_candidate_dashboard_routes(app, dashboard_helpers)
    register_employer_dashboard_routes(app, dashboard_helpers)

    @app.route('/')
    def home():
        return render_template('index.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')

            user = User.query.filter_by(email=email, password=password).first()
            if not user:
                flash('Invalid credentials', 'error')
                return render_template('login.html')

            user.role = normalize_role(user.role)
            session['user_id'] = user.id
            session['role'] = user.role

            record_login_event(user, provider='local', is_new_user=False)
            db.session.commit()

            destination = next_step_endpoint_for_user(user)
            if destination in ('candidate_form', 'employer_form'):
                flash('Login successful. Please complete your profile details first.', 'success')
            else:
                flash('Login successful!', 'success')
            return redirect(url_for(destination))
        return render_template('login.html')

    @app.route('/signup')
    def signup():
        return render_template('signup.html', active_role='candidate')

    @app.route('/signup/candidate', methods=['GET', 'POST'])
    def signup_candidate():
        if request.method == 'GET':
            return render_template('signup.html', active_role='candidate')

        if request.method == 'POST':
            full_name = first_non_empty(
                [
                    request.form.get('full_name', ''),
                    request.form.get('name', ''),
                ]
            )
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            skills = request.form.get('skills', '').strip()
            education = request.form.get('education', '').strip()
            experience = first_non_empty(
                [
                    request.form.get('experience', ''),
                    education,
                ]
            )

            if not full_name or not email or not password:
                flash('Full name, email and password are required.', 'error')
            elif confirm_password and password != confirm_password:
                flash('Password and confirm password do not match.', 'error')
            else:
                try:
                    new_user, error_message = create_local_user(
                        role='candidate',
                        email=email,
                        password=password,
                        username=username,
                        full_name=full_name,
                    )
                    if error_message:
                        flash(error_message, 'error')
                    else:
                        profile = CandidateProfile(user_id=new_user.id)
                        profile.name = full_name
                        profile.email = email
                        profile.skills = skills
                        profile.experience = experience
                        db.session.add(profile)

                        session['user_id'] = new_user.id
                        session['role'] = 'candidate'
                        record_login_event(new_user, provider='local', is_new_user=True)

                        db.session.commit()
                        flash('Candidate account created successfully!', 'success')
                        return redirect(url_for('candidate_dashboard'))
                except Exception:
                    db.session.rollback()
                    app.logger.exception('Candidate signup failed')
                    flash('Unable to create candidate account right now. Please try again.', 'error')
        return render_template('signup.html', active_role='candidate')

    @app.route('/signup/employer', methods=['GET', 'POST'])
    def signup_employer():
        if request.method == 'GET':
            return render_template('signup.html', active_role='employer')

        if request.method == 'POST':
            company_name = request.form.get('company_name', '').strip()
            hr_name = first_non_empty(
                [
                    request.form.get('hr_name', ''),
                    request.form.get('designation', ''),
                ]
            )
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            company_size = request.form.get('company_size', '').strip()

            if not company_name or not hr_name or not email or not password:
                flash('Company name, HR name, email and password are required.', 'error')
            elif confirm_password and password != confirm_password:
                flash('Password and confirm password do not match.', 'error')
            else:
                try:
                    username_source = username or company_name
                    new_user, error_message = create_local_user(
                        role='employer',
                        email=email,
                        password=password,
                        username=username_source,
                        full_name=hr_name,
                    )
                    if error_message:
                        flash(error_message, 'error')
                    else:
                        profile = EmployerProfile(user_id=new_user.id)
                        profile.company_name = company_name
                        profile.hr_name = hr_name
                        profile.email = email
                        profile.company_size = company_size
                        db.session.add(profile)

                        session['user_id'] = new_user.id
                        session['role'] = 'employer'
                        record_login_event(new_user, provider='local', is_new_user=True)

                        db.session.commit()
                        flash('Employer account created successfully!', 'success')
                        return redirect(url_for('employer_dashboard'))
                except Exception:
                    db.session.rollback()
                    app.logger.exception('Employer signup failed')
                    flash('Unable to create employer account right now. Please try again.', 'error')
        return render_template('signup.html', active_role='employer')

    @app.route('/auth/google')
    def google_login():
        client_id = app.config.get('GOOGLE_CLIENT_ID')
        if not client_id:
            flash('Google login is not configured yet. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.', 'error')
            return redirect(url_for('login'))

        session['oauth_role'] = normalize_role(request.args.get('role', 'jobseeker'))
        state = secrets.token_urlsafe(24)
        session['google_oauth_state'] = state

        try:
            discovery = fetch_json(app.config['GOOGLE_DISCOVERY_URL'])
            authorization_endpoint = discovery.get('authorization_endpoint')
            if not authorization_endpoint:
                raise RuntimeError('Missing Google authorization endpoint')

            query = urlencode(
                {
                    'client_id': client_id,
                    'redirect_uri': google_redirect_uri(),
                    'scope': 'openid email profile',
                    'response_type': 'code',
                    'state': state,
                    'prompt': 'select_account',
                }
            )
            return redirect(f'{authorization_endpoint}?{query}')
        except Exception:
            app.logger.exception('Unable to start Google OAuth flow')
            flash('Unable to start Google login right now. Please try again.', 'error')
            return redirect(url_for('login'))

    @app.route('/auth/google/callback')
    def google_callback():
        incoming_state = request.args.get('state')
        expected_state = session.pop('google_oauth_state', None)

        if not incoming_state or incoming_state != expected_state:
            flash('Google login failed (invalid session state). Please try again.', 'error')
            return redirect(url_for('login'))

        if request.args.get('error'):
            flash('Google login was cancelled or denied.', 'error')
            return redirect(url_for('login'))

        code = request.args.get('code')
        if not code:
            flash('Google login failed because no code was returned.', 'error')
            return redirect(url_for('login'))

        client_id = app.config.get('GOOGLE_CLIENT_ID')
        client_secret = app.config.get('GOOGLE_CLIENT_SECRET')
        if not client_id or not client_secret:
            flash('Google login is not configured yet. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.', 'error')
            return redirect(url_for('login'))

        selected_role = normalize_role(session.pop('oauth_role', 'candidate'))

        try:
            discovery = fetch_json(app.config['GOOGLE_DISCOVERY_URL'])
            token_endpoint = discovery.get('token_endpoint')
            userinfo_endpoint = discovery.get('userinfo_endpoint')
            if not token_endpoint or not userinfo_endpoint:
                raise RuntimeError('Missing Google token or userinfo endpoint')

            token_payload = post_form_json(
                token_endpoint,
                {
                    'code': code,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': google_redirect_uri(),
                    'grant_type': 'authorization_code',
                },
            )
            access_token = token_payload.get('access_token')
            if not access_token:
                raise RuntimeError('Google token response did not include an access token')

            user_info = fetch_json(
                userinfo_endpoint,
                headers={'Authorization': f'Bearer {access_token}'},
            )
            email = (user_info.get('email') or '').strip().lower()
            google_sub = (user_info.get('sub') or '').strip()
            if not email:
                raise RuntimeError('Google userinfo did not include an email address')

            display_name = (user_info.get('name') or email.split('@')[0]).strip()

            user = None
            if google_sub:
                user = User.query.filter_by(google_sub=google_sub).first()
            if user is None:
                user = User.query.filter_by(email=email).first()

            is_new_user = user is None
            if is_new_user:
                username = build_unique_username(display_name)
                generated_password = f'google-oauth-{secrets.token_urlsafe(24)}'
                user = User(
                    username=username,
                    email=email,
                    password=generated_password,
                    role=selected_role,
                    auth_provider='google',
                    google_sub=google_sub or None,
                    full_name=display_name,
                )
                db.session.add(user)
                db.session.flush()
            else:
                user.role = resolve_role_for_existing_google_user(user, selected_role)
                if display_name and not user.full_name:
                    user.full_name = display_name
                if google_sub and not user.google_sub:
                    user.google_sub = google_sub
                if not user.auth_provider:
                    user.auth_provider = 'google'

            record_login_event(user, provider='google', is_new_user=is_new_user)
            db.session.commit()

            session['user_id'] = user.id
            session['role'] = user.role

            destination = next_step_endpoint_for_user(user)
            if is_new_user:
                flash('Google login successful! Please complete your profile details.', 'success')
            elif destination in ('candidate_form', 'employer_form'):
                flash('Welcome back. Please complete your remaining profile details.', 'success')
            else:
                flash('Logged in with Google successfully!', 'success')
            return redirect(url_for(destination))
        except Exception:
            db.session.rollback()
            app.logger.exception('Google OAuth callback failed')
            flash('Google login failed. Please try again.', 'error')
            return redirect(url_for('login'))

    @app.route('/price')
    def price():
        return render_template('price.html')

    @app.route('/skill')
    def skill():
        return render_template('skill.html')

    @app.route('/auth')
    def auth():
        return render_template('auth.html')

    @app.route('/auth/linkedin')
    def linkedin_login():
        flash('LinkedIn login will be available soon. Please continue with Google for now.', 'error')
        return redirect(url_for('login'))

    @app.route('/auth/phone')
    def phone_login():
        flash('Phone login will be available soon. Please continue with Google for now.', 'error')
        return redirect(url_for('login'))

    @app.route('/forgot-password')
    def forgot_password():
        flash('Forgot password is not set up yet. Please use your existing password.', 'error')
        return redirect(url_for('login'))

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('home'))
