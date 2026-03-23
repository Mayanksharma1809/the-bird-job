import json
import re
from datetime import datetime
from io import BytesIO
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from flask import flash, redirect, render_template, request, url_for

from models import CandidateJobAction, CandidateProfile, User, db


def register_candidate_dashboard_routes(app, helpers):
    get_logged_in_user = helpers['get_logged_in_user']
    normalize_role = helpers['normalize_role']
    dashboard_endpoint_for_role = helpers['dashboard_endpoint_for_role']
    first_non_empty = helpers['first_non_empty']
    candidate_dashboard_user = helpers['candidate_dashboard_user']
    has_completed_profile = helpers['has_completed_profile']

    def parse_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def profile_completion_score(profile):
        if profile is None:
            return 0

        checks = [
            profile.name,
            profile.email,
            profile.phone,
            profile.skills,
            profile.experience,
        ]
        completed = sum(1 for field in checks if (field or '').strip())
        return int((completed / len(checks)) * 100)

    def get_text(data, keys, fallback=''):
        for key in keys:
            value = data.get(key) if isinstance(data, dict) else None
            cleaned = str(value or '').strip()
            if cleaned:
                return cleaned
        return fallback

    def extract_raw_jobs(payload):
        if isinstance(payload, list):
            return payload

        if not isinstance(payload, dict):
            return []

        direct_keys = ('jobs', 'data', 'results', 'items')
        nested_keys = ('jobs', 'data', 'results', 'items')

        for key in direct_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                for nested_key in nested_keys:
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, list):
                        return nested_value

        return []

    def build_api_sources():
        sources = []
        configured = [
            app.config.get('JOBS_API_URL'),
            app.config.get('JOBS_API_URL_2'),
            *(app.config.get('JOBS_API_URLS') or []),
        ]
        for entry in configured:
            url = (entry or '').strip()
            if url and url not in sources:
                sources.append(url)
        return sources

    def source_label(base_url, index):
        host = (urlparse(base_url).netloc or '').strip().lower()
        if host:
            return host.replace('www.', '')
        return f'api{index}'

    def normalize_job_item(item, source):
        if not isinstance(item, dict):
            return None

        title = get_text(item, ('title', 'job_title', 'position', 'name'))
        if not title:
            return None

        company_name = get_text(
            item,
            ('company_name', 'company', 'companyName', 'employer_name', 'organization'),
            fallback='Confidential Company',
        )
        job_location = get_text(
            item,
            ('candidate_required_location', 'location', 'job_location', 'city', 'country'),
            fallback='Location not specified',
        )
        salary = get_text(
            item,
            ('salary', 'salary_range', 'compensation', 'pay'),
            fallback='Salary not disclosed',
        )
        job_type = get_text(
            item,
            ('job_type', 'employment_type', 'type'),
            fallback='Full-time',
        )
        job_url = get_text(item, ('url', 'job_url', 'apply_url', 'apply_link'))
        external_job_id = get_text(item, ('id', 'job_id', 'uuid', 'external_id'))
        if not external_job_id:
            external_job_id = job_url or f'{title}:{company_name}:{job_location}:{source}'

        return {
            'id': str(external_job_id).strip(),
            'title': title,
            'company_name': company_name,
            'location': job_location,
            'salary': salary,
            'job_type': job_type,
            'url': job_url,
            'source': source,
        }

    def fetch_jobs_from_endpoint(base_url, search, timeout, source):
        query = {}
        if search:
            # Keep query broad for compatibility across different APIs.
            query['search'] = search
            query['q'] = search

        endpoint = base_url
        if query:
            separator = '&' if '?' in base_url else '?'
            endpoint = f'{base_url}{separator}{urlencode(query)}'

        try:
            req = Request(
                endpoint,
                headers={
                    'Accept': 'application/json',
                    'User-Agent': 'TheBirdJob/1.0',
                },
            )
            with urlopen(req, timeout=timeout) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except (URLError, OSError, json.JSONDecodeError):
            return [], False

        normalized_jobs = []
        for item in extract_raw_jobs(payload):
            job = normalize_job_item(item, source)
            if job is not None:
                normalized_jobs.append(job)
        return normalized_jobs, True

    def dedupe_key(job):
        job_url = (job.get('url') or '').strip().lower()
        if job_url:
            return ('url', job_url)

        return (
            'text',
            (job.get('title') or '').strip().lower(),
            (job.get('company_name') or '').strip().lower(),
            (job.get('location') or '').strip().lower(),
        )

    def fetch_jobs_from_api(search='', location='', level=''):
        api_sources = build_api_sources()
        if not api_sources:
            return [], 'Jobs API URL is not configured.'

        timeout = parse_int(app.config.get('JOBS_API_TIMEOUT'), 10)
        limit = parse_int(app.config.get('CANDIDATE_DASHBOARD_JOB_LIMIT'), 12)
        search = (search or '').strip()
        location = (location or '').strip().lower()
        level = (level or '').strip().lower()

        level_tokens = {
            'fresher': ('fresher', 'intern', 'entry', 'junior'),
            '1-3 years': ('junior', 'associate', '1', '2', '3'),
            '3-5 years': ('mid', '3', '4', '5'),
            '5+ years': ('senior', 'lead', 'principal', 'staff', '5', '6', '7', '8', '9'),
        }
        selected_tokens = level_tokens.get(level, ())

        jobs = []
        seen_keys = set()
        failed_sources = 0

        for index, base_url in enumerate(api_sources, start=1):
            source = source_label(base_url, index)
            source_jobs, success = fetch_jobs_from_endpoint(base_url, search, timeout, source)
            if not success:
                failed_sources += 1
                continue

            for job in source_jobs:
                searchable = f"{job['title']} {job['company_name']} {job['location']} {job['job_type']}".lower()
                if location and location not in searchable:
                    continue
                if selected_tokens and not any(token in searchable for token in selected_tokens):
                    continue

                key = dedupe_key(job)
                if key in seen_keys:
                    continue

                seen_keys.add(key)
                jobs.append(job)

                if len(jobs) >= limit:
                    break

            if len(jobs) >= limit:
                break

        if not jobs and failed_sources == len(api_sources):
            return [], 'Unable to load jobs from APIs right now. Please try again.'

        return jobs, None

    def build_candidate_dashboard_stats(user, jobs):
        profile = CandidateProfile.query.filter_by(user_id=user.id).first()
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        applied_count = CandidateJobAction.query.filter(
            CandidateJobAction.candidate_user_id == user.id,
            CandidateJobAction.action == 'applied',
            CandidateJobAction.created_at >= month_start,
        ).count()
        saved_count = CandidateJobAction.query.filter_by(candidate_user_id=user.id, action='saved').count()
        completion = profile_completion_score(profile)

        return {
            'open_matches': len(jobs),
            'applications_submitted': applied_count,
            'saved_jobs': saved_count,
            'profile_strength': f'{completion}%',
            'profile_completion': f'{completion}%',
        }

    def build_candidate_redirect():
        query = {}
        q = request.form.get('search_q', request.form.get('q', '')).strip()
        location = request.form.get('search_location', '').strip()
        level = request.form.get('search_level', '').strip()
        if q:
            query['q'] = q
        if location:
            query['location'] = location
        if level:
            query['level'] = level
        return redirect(url_for('candidate_dashboard', **query))

    def clean_document_text(text):
        text = str(text or '').replace('\x00', ' ')
        text = re.sub(r'\r\n?', '\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def decode_text_bytes(raw_bytes):
        for encoding in ('utf-8', 'utf-16', 'latin-1'):
            try:
                return raw_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw_bytes.decode('utf-8', errors='ignore')

    def extract_docx_text(raw_bytes):
        try:
            with ZipFile(BytesIO(raw_bytes)) as archive:
                document_xml = archive.read('word/document.xml')
        except (BadZipFile, KeyError):
            return ''

        root = ET.fromstring(document_xml)
        text_chunks = []
        for element in root.iter():
            if element.tag.endswith('}t') and element.text:
                text_chunks.append(element.text)
            elif element.tag.endswith('}p'):
                text_chunks.append('\n')
        return clean_document_text(' '.join(text_chunks))

    def extract_pdf_text(raw_bytes):
        for module_name in ('pypdf', 'PyPDF2'):
            try:
                module = __import__(module_name, fromlist=['PdfReader'])
                reader = module.PdfReader(BytesIO(raw_bytes))
                text = '\n'.join((page.extract_text() or '') for page in reader.pages)
                text = clean_document_text(text)
                if text:
                    return text, None
            except Exception:
                continue

        return '', 'PDF text extraction is unavailable on this server right now. Please upload DOCX/TXT or paste the job description.'

    def extract_uploaded_text(uploaded_file, label):
        filename = (uploaded_file.filename or '').strip()
        if not filename:
            return '', f'{label} file is missing a filename.'

        raw_bytes = uploaded_file.read()
        uploaded_file.stream.seek(0)

        if not raw_bytes:
            return '', f'{label} file is empty.'

        lower_name = filename.lower()

        if lower_name.endswith('.docx'):
            text = extract_docx_text(raw_bytes)
            if text:
                return text, None
            return '', f'Unable to read text from the {label.lower()} DOCX file.'

        if lower_name.endswith('.pdf'):
            return extract_pdf_text(raw_bytes)

        text = clean_document_text(decode_text_bytes(raw_bytes))
        if not text:
            return '', f'Unable to read text from the {label.lower()} file.'

        if lower_name.endswith('.doc') and len(re.sub(r'[^A-Za-z0-9\s]', '', text)) < 80:
            return '', f'Legacy .doc files are not supported reliably for {label.lower()} uploads. Please use PDF, DOCX, or TXT.'

        return text, None

    @app.route('/candidate_dashboard')
    def candidate_dashboard():
        user = get_logged_in_user()
        if user is None or normalize_role(user.role) != 'candidate':
            return redirect(url_for('login'))
        if not has_completed_profile(user):
            flash('Please complete your candidate profile first.', 'error')
            return redirect(url_for('candidate_form'))

        search_query = request.args.get('q', '').strip()
        search_location = request.args.get('location', '').strip()
        search_level = request.args.get('level', '').strip()
        jobs, jobs_error = fetch_jobs_from_api(search_query, search_location, search_level)

        stats = build_candidate_dashboard_stats(user, jobs)
        recent_applications = CandidateJobAction.query.filter_by(
            candidate_user_id=user.id,
            action='applied',
        ).order_by(CandidateJobAction.created_at.desc()).limit(5).all()

        return render_template(
            'candidate_dashboard.html',
            user=candidate_dashboard_user(user),
            jobs=jobs,
            jobs_error=jobs_error,
            stats=stats,
            recent_applications=recent_applications,
            search={
                'q': search_query,
                'location': search_location,
                'level': search_level,
            },
        )

    @app.route('/candidate/jobs/action', methods=['POST'])
    def candidate_job_action():
        user = get_logged_in_user()
        if user is None or normalize_role(user.role) != 'candidate':
            return redirect(url_for('login'))

        raw_action = (request.form.get('action') or '').strip().lower()
        action = 'applied' if raw_action == 'apply' else 'saved' if raw_action == 'save' else ''
        if not action:
            flash('Invalid job action.', 'error')
            return build_candidate_redirect()

        job_title = request.form.get('job_title', '').strip()
        company_name = request.form.get('company_name', '').strip()
        location = request.form.get('job_location', '').strip()
        salary = request.form.get('salary', '').strip()
        job_url = request.form.get('job_url', '').strip()
        external_job_id = request.form.get('external_job_id', '').strip()
        source = (request.form.get('source') or 'api').strip().lower()

        if not job_title:
            flash('Job title is required to continue.', 'error')
            return build_candidate_redirect()

        existing = None
        if external_job_id:
            existing = CandidateJobAction.query.filter_by(
                candidate_user_id=user.id,
                external_job_id=external_job_id,
                action=action,
            ).first()
        if existing is None:
            existing = CandidateJobAction.query.filter_by(
                candidate_user_id=user.id,
                job_title=job_title,
                company_name=company_name,
                action=action,
            ).first()

        if existing is not None:
            flash(f'Job already {action}.', 'success')
            return build_candidate_redirect()

        new_action = CandidateJobAction(
            candidate_user_id=user.id,
            source=source or 'api',
            external_job_id=external_job_id or None,
            job_title=job_title,
            company_name=company_name or None,
            location=location or None,
            salary=salary or None,
            job_url=job_url or None,
            action=action,
            status='submitted' if action == 'applied' else 'saved',
        )
        try:
            db.session.add(new_action)
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception('Failed to persist candidate job action')
            flash('Unable to save this job action right now. Please try again.', 'error')
            return build_candidate_redirect()

        flash('Job action saved successfully.', 'success')
        return build_candidate_redirect()

    @app.route('/candidate_form', methods=['GET', 'POST'])
    def candidate_form():
        user = get_logged_in_user()
        if user is None:
            flash('Please login first.', 'error')
            return redirect(url_for('login'))
        if normalize_role(user.role) != 'candidate':
            return redirect(url_for(dashboard_endpoint_for_role(user.role)))

        profile = CandidateProfile.query.filter_by(user_id=user.id).first()
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            primary_email = request.form.get('email', '').strip().lower()
            account_email = request.form.get('account_email', '').strip().lower()
            email = first_non_empty([account_email, primary_email]).lower()
            phone = request.form.get('phone', '').strip()
            skills = request.form.get('skills', '').strip()
            experience = request.form.get('experience', '').strip()
            password = request.form.get('password', '').strip()

            if not name or not email:
                flash('Name and email are required.', 'error')
            else:
                email_owner = User.query.filter(User.email == email, User.id != user.id).first()
                if email_owner:
                    flash('This email is already used by another account.', 'error')
                    return render_template(
                        'candidateform.html',
                        oauth_data={'name': name, 'email': email},
                    )

                if profile is None:
                    profile = CandidateProfile(user_id=user.id)
                profile.name = name
                profile.email = email
                profile.phone = phone
                profile.skills = skills
                profile.experience = experience
                user.email = email
                user.full_name = name
                if password:
                    user.password = password
                db.session.add(profile)
                db.session.commit()
                flash('Candidate profile saved successfully.', 'success')
                return redirect(url_for('candidate_dashboard'))

        oauth_data = {
            'name': profile.name if profile else (user.full_name or user.username),
            'email': profile.email if profile else user.email,
        }
        return render_template('candidateform.html', oauth_data=oauth_data)

    # ===== ATS SCANNER ROUTES =====
    
    @app.route('/candidate/ats_scanner')
    def ats_scanner_page():
        """Display the ATS scanner page."""
        user = get_logged_in_user()
        if user is None or normalize_role(user.role) != 'candidate':
            return redirect(url_for('login'))
        if not has_completed_profile(user):
            flash('Please complete your candidate profile first.', 'error')
            return redirect(url_for('candidate_form'))

        dashboard_user = candidate_dashboard_user(user)
        return render_template('Ats_scanner.html', user=dashboard_user)

    @app.route('/candidate/ats/scan-legacy', methods=['POST'])
    def ats_scan_resume():
        """Handle ATS scanner file upload and analysis."""
        user = get_logged_in_user()
        if user is None or normalize_role(user.role) != 'candidate':
            return {'success': False, 'error': 'Unauthorized'}, 401

        if 'resume' not in request.files:
            return {'success': False, 'error': 'No resume file provided'}, 400

        resume_file = request.files['resume']
        if resume_file.filename == '':
            return {'success': False, 'error': 'No file selected'}, 400

        job_description = (request.form.get('job_description') or '').strip()
        job_description_file = request.files.get('job_description_file')

        try:
            resume_text, resume_error = extract_uploaded_text(resume_file, 'Resume')
            if resume_error:
                return {'success': False, 'error': resume_error}, 400

            if not resume_text:
                return {'success': False, 'error': 'Resume file is empty'}, 400

            if job_description_file and (job_description_file.filename or '').strip():
                jd_file_text, jd_error = extract_uploaded_text(job_description_file, 'Job description')
                if jd_error:
                    return {'success': False, 'error': jd_error}, 400
                if job_description:
                    job_description = f'{job_description}\n\n{jd_file_text}'
                else:
                    job_description = jd_file_text

            if not job_description:
                return {'success': False, 'error': 'Please paste or upload the job description.'}, 400

            from ai_helper import analyze_resume_with_backup

            analysis, provider_used, used_fallback = analyze_resume_with_backup(
                resume_text,
                job_description,
                preferred_provider='groq'
            )

            score = analysis.get('score', 0)
            source_note = (
                'Backup ATS scoring was used because AI providers were unavailable.'
                if used_fallback else
                f'Analyzed with {provider_used.upper()} AI.'
            )
            fallback_reason = analysis.get('fallback_reason')

            return {
                'success': True,
                'score': score,
                'resume_text': resume_text,
                'job_description_text': job_description,
                'feedback': analysis.get('feedback', []),
                'strengths': analysis.get('strengths', []),
                'issues': analysis.get('issues', []),
                'present_keywords': analysis.get('present_keywords', []),
                'missing_keywords': analysis.get('missing_keywords', []),
                'breakdown': analysis.get('breakdown', {}),
                'message': f'Your resume scored {score}% ATS compatibility!',
                'provider': provider_used,
                'analysis_mode': 'fallback' if used_fallback else 'ai',
                'source_note': source_note,
                'fallback_reason': fallback_reason,
            }, 200

        except Exception as e:
            app.logger.exception('ATS scan failed')
            return {'success': False, 'error': f'Unable to process resume: {str(e)}'}, 500
