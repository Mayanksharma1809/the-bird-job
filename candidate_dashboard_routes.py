import json
import re
from datetime import datetime, timedelta
from io import BytesIO
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from flask import flash, jsonify, redirect, render_template, request, url_for

from models import (
    CandidateJobAction,
    CandidateProfile,
    EmployerJob,
    EmployerProfile,
    Message,
    PortfolioItem,
    User,
    db
)


def register_candidate_dashboard_routes(app, helpers):
    get_logged_in_user = helpers['get_logged_in_user']
    normalize_role = helpers['normalize_role']
    dashboard_endpoint_for_role = helpers['dashboard_endpoint_for_role']
    first_non_empty = helpers['first_non_empty']
    candidate_dashboard_user = helpers['candidate_dashboard_user']
    has_completed_profile = helpers['has_completed_profile']

    def ensure_candidate_access(require_profile=True):
        user = get_logged_in_user()
        if user is None:
            flash('Please login first.', 'error')
            return None, redirect(url_for('login'))
        if normalize_role(user.role) != 'candidate':
            return None, redirect(url_for(dashboard_endpoint_for_role(user.role)))
        if require_profile and not has_completed_profile(user):
            flash('Please complete your candidate profile first.', 'error')
            return None, redirect(url_for('candidate_form'))
        return user, None

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
        timeout = parse_int(app.config.get('JOBS_API_TIMEOUT'), 10)
        limit = parse_int(app.config.get('CANDIDATE_DASHBOARD_JOB_LIMIT'), 12)
        visibility_days = max(parse_int(app.config.get('EMPLOYER_JOB_VISIBILITY_DAYS'), 30), 1)
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

        # Include employer-posted jobs for candidate visibility window.
        visibility_cutoff = datetime.utcnow() - timedelta(days=visibility_days)
        employer_jobs = (
            EmployerJob.query
            .filter(
                EmployerJob.status == 'active',
                EmployerJob.created_at >= visibility_cutoff,
            )
            .order_by(EmployerJob.created_at.desc())
            .all()
        )
        for employer_job in employer_jobs:
            employer_profile = employer_job.employer.employer_profile if employer_job.employer else None
            company_name = get_text(
                {
                    'company_name': employer_profile.company_name if employer_profile else '',
                    'company': employer_job.employer.full_name if employer_job.employer else '',
                },
                ('company_name', 'company'),
                fallback='Employer',
            )
            normalized = {
                'id': f'employer-{employer_job.id}',
                'employer_job_id': employer_job.id,
                'title': employer_job.title,
                'company_name': company_name,
                'location': employer_job.location or 'Location not specified',
                'salary': employer_job.salary or 'Salary not disclosed',
                'job_type': employer_job.job_type or 'Full-time',
                'url': '',
                'source': 'employer',
            }

            searchable = f"{normalized['title']} {normalized['company_name']} {normalized['location']} {normalized['job_type']}".lower()
            if search and search.lower() not in searchable:
                continue
            if location and location not in searchable:
                continue
            if selected_tokens and not any(token in searchable for token in selected_tokens):
                continue

            key = dedupe_key(normalized)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            jobs.append(normalized)
            if len(jobs) >= limit:
                return jobs, None

        api_sources = build_api_sources()
        if not api_sources:
            if jobs:
                return jobs, None
            return [], 'Jobs API URL is not configured.'

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
            portfolio_items=user.portfolio_items,
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
        employer_job_id = parse_int(request.form.get('employer_job_id', '').strip(), default=None)

        if not job_title:
            flash('Job title is required to continue.', 'error')
            return build_candidate_redirect()

        existing = None
        if employer_job_id:
            existing = CandidateJobAction.query.filter_by(
                candidate_user_id=user.id,
                employer_job_id=employer_job_id,
                action=action,
            ).first()
        if existing is None and external_job_id:
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
            employer_job_id=employer_job_id,
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
        
        # If external job, redirect to original link
        if action == 'applied' and not employer_job_id and job_url:
            return redirect(job_url)

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
            experience_years = request.form.get('experience_years', '').strip()
            education_level = request.form.get('education_level', '').strip()
            specialization = request.form.get('specialization', '').strip()
            location = request.form.get('location', '').strip()
            job_title = request.form.get('job_title', '').strip()
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
                profile.experience_years = experience_years
                profile.education_level = education_level
                profile.specialization = specialization
                profile.location = location
                profile.job_title = job_title
                
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
            'phone': profile.phone if profile else '',
            'skills': profile.skills if profile else '',
            'experience': profile.experience if profile else '',
            'experience_years': profile.experience_years if profile else '',
            'education_level': profile.education_level if profile else '',
            'specialization': profile.specialization if profile else '',
            'location': profile.location if profile else '',
            'job_title': profile.job_title if profile else '',
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

    @app.route('/candidate_pricing')
    def candidate_pricing_page():
        """Display the pricing plans for candidates."""
        user = get_logged_in_user()
        if user is None or normalize_role(user.role) != 'candidate':
            # Optionally show public pricing if not logged in
            return render_template('candidate_pricing.html')
        
        dashboard_user = candidate_dashboard_user(user)
        return render_template('candidate_pricing.html', user=dashboard_user)

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

    def candidate_conversations_data(user):
        # Users I've talked to
        sent_to = [r[0] for r in db.session.query(Message.receiver_id).filter_by(sender_id=user.id).all()]
        received_from = [r[0] for r in db.session.query(Message.sender_id).filter_by(receiver_id=user.id).all()]
        
        # Employers I applied to
        applied_employer_ids = [
            r[0] for r in db.session.query(EmployerJob.employer_user_id)
            .join(CandidateJobAction, CandidateJobAction.employer_job_id == EmployerJob.id)
            .filter(CandidateJobAction.candidate_user_id == user.id, CandidateJobAction.action == 'applied')
            .all()
        ]
        
        participant_ids = list(set(sent_to + received_from + applied_employer_ids))
        conversations = []
        
        for p_id in participant_ids:
            if not p_id: continue
            participant = User.query.get(p_id)
            if not participant: continue
            
            last_msg = (
                Message.query.filter(
                    ((Message.sender_id == user.id) & (Message.receiver_id == p_id)) |
                    ((Message.sender_id == p_id) & (Message.receiver_id == user.id))
                )
                .order_by(Message.timestamp.desc())
                .first()
            )
            
            unread_count = Message.query.filter_by(
                sender_id=p_id, receiver_id=user.id, is_read=False
            ).count()
            
            profile = participant.employer_profile
            
            # Find most recent job applied to with this employer
            latest_app = (
                CandidateJobAction.query
                .join(EmployerJob, CandidateJobAction.employer_job_id == EmployerJob.id)
                .filter(CandidateJobAction.candidate_user_id == user.id, EmployerJob.employer_user_id == p_id)
                .order_by(CandidateJobAction.created_at.desc())
                .first()
            )
            
            role_desc = latest_app.job_title if latest_app else "Employer"
            
            conversations.append({
                'id': participant.id,
                'name': profile.company_name if profile else (participant.full_name or participant.username),
                'role': role_desc,
                'last_message': last_msg.content if last_msg else 'Start a conversation',
                'last_time': last_msg.timestamp.isoformat() if last_msg else (latest_app.created_at.isoformat() if latest_app else ''),
                'unread_count': unread_count,
                'initials': (profile.company_name if profile else (participant.full_name or participant.username or '??'))[:2].upper()
            })
            
        conversations.sort(key=lambda x: x['last_time'], reverse=True)
        return conversations

    @app.route('/candidate_messages')
    def candidate_messages_page():
        user, redirect_response = ensure_candidate_access(require_profile=True)
        if user is None:
            return redirect_response
        
        conversations = candidate_conversations_data(user)
        return render_template(
            'candidate_massage.html',
            user=candidate_dashboard_user(user),
            conversations=conversations
        )

    @app.route('/candidate/portfolio')
    def candidate_portfolio_page():
        user, redirect_response = ensure_candidate_access(require_profile=True)
        if user is None:
            return redirect_response
            
        return render_template(
            'candidate_portfolio.html',
            user=candidate_dashboard_user(user),
            portfolio_items=user.portfolio_items
        )

    @app.route('/candidate_applications')
    def candidate_applications_page():
        user, redirect_response = ensure_candidate_access(require_profile=True)
        if user is None:
            return redirect_response
        
        all_apps = CandidateJobAction.query.filter_by(
            candidate_user_id=user.id,
            action='applied',
        ).order_by(CandidateJobAction.created_at.desc()).all()
        
        return render_template(
            'candidate_applications.html',
            user=candidate_dashboard_user(user),
            applications=all_apps
        )

    @app.route('/api/candidate/conversations')
    def get_candidate_conversations_api():
        user = get_logged_in_user()
        if not user or normalize_role(user.role) != 'candidate':
            return jsonify([]), 401
        return jsonify(candidate_conversations_data(user))

    @app.route('/api/candidate/messages/<int:employer_id>')
    def get_candidate_chat_messages(employer_id):
        user = get_logged_in_user()
        if not user or normalize_role(user.role) != 'candidate':
            return jsonify([]), 401
            
        messages = Message.query.filter(
            ((Message.sender_id == user.id) & (Message.receiver_id == employer_id)) |
            ((Message.sender_id == employer_id) & (Message.receiver_id == user.id))
        ).order_by(Message.timestamp.asc()).all()
        
        Message.query.filter_by(sender_id=employer_id, receiver_id=user.id, is_read=False).update({'is_read': True})
        db.session.commit()
        
        return jsonify([{
            'id': m.id,
            'sender_id': m.sender_id,
            'content': m.content,
            'timestamp': m.timestamp.isoformat(),
            'mine': m.sender_id == user.id
        } for m in messages])

    @app.route('/api/candidate/messages/send', methods=['POST'])
    def send_candidate_message():
        user = get_logged_in_user()
        if not user or normalize_role(user.role) != 'candidate':
            return jsonify({'error': 'Unauthorized'}), 401
            
        data = request.json or {}
        employer_id = data.get('employer_id')
        content = data.get('content')
        
        if not employer_id or not content:
            return jsonify({'error': 'Invalid data'}), 400
            
        msg = Message(sender_id=user.id, receiver_id=employer_id, content=content)
        db.session.add(msg)
        db.session.commit()
        
        return jsonify({
            'id': msg.id,
            'sender_id': msg.sender_id,
            'content': msg.content,
            'timestamp': msg.timestamp.isoformat(),
            'mine': True
        })

    # ===== PORTFOLIO ROUTES =====

    @app.route('/candidate/portfolio/upload', methods=['POST'])
    def upload_portfolio_item():
        user, redirect_response = ensure_candidate_access(require_profile=True)
        if user is None:
            return redirect_response

        # Check total seats (5 seats limit)
        existing_items_count = PortfolioItem.query.filter_by(candidate_user_id=user.id).count()
        if existing_items_count >= 5:
            flash('You have reached the limit of 5 portfolio seats. Please delete an item to upload a new one.', 'error')
            return redirect(url_for('candidate_dashboard'))

        item_type = request.form.get('item_type', 'certificate') # 'resume' or 'certificate'
        label = request.form.get('label', '').strip()
        uploaded_file = request.files.get('file')

        if item_type == 'resume':
            flash('Resumes must be uploaded via the ATS Scanner to verify your score! 🤖', 'error')
            return redirect(url_for('candidate_portfolio_page'))

        if not uploaded_file or not label:
            flash('File and label are required.', 'error')
            return redirect(url_for('candidate_portfolio_page'))

        # Check if already has a main resume seat filled if this is a resume
        if item_type == 'resume':
            existing_resume = PortfolioItem.query.filter_by(candidate_user_id=user.id, item_type='resume').first()
            if existing_resume:
                flash('You already have a resume in your portfolio. Only 1 resume seat is allowed.', 'error')
                return redirect(url_for('candidate_dashboard'))

        filename = uploaded_file.filename
        content = uploaded_file.read()
        content_type = uploaded_file.content_type

        new_item = PortfolioItem(
            candidate_user_id=user.id,
            label=label,
            item_type=item_type,
            file_name=filename,
            file_content=content,
            content_type=content_type
        )
        
        try:
            db.session.add(new_item)
            db.session.commit()
            flash(f'Portfolio {item_type} "{label}" uploaded successfully!', 'success')
        except Exception:
            db.session.rollback()
            app.logger.exception('Portfolio upload failed')
            flash('Unable to upload portfolio item right now.', 'error')

        return redirect(url_for('candidate_dashboard'))

    @app.route('/candidate/portfolio/view/<int:item_id>')
    def view_portfolio_item(item_id):
        user = get_logged_in_user()
        if not user or normalize_role(user.role) != 'candidate':
            return redirect(url_for('login'))

        item = PortfolioItem.query.filter_by(id=item_id, candidate_user_id=user.id).first()
        if not item:
            flash('Portfolio item not found.', 'error')
            return redirect(url_for('candidate_dashboard'))

        from flask import Response
        return Response(
            item.file_content,
            mimetype=item.content_type,
            headers={"Content-disposition": f"inline; filename={item.file_name}"}
        )

    @app.route('/candidate/portfolio/delete/<int:item_id>', methods=['POST'])
    def delete_portfolio_item(item_id):
        user = get_logged_in_user()
        if not user or normalize_role(user.role) != 'candidate':
            return redirect(url_for('login'))

        item = PortfolioItem.query.filter_by(id=item_id, candidate_user_id=user.id).first()
        if item:
            db.session.delete(item)
            db.session.commit()
            flash('Portfolio item deleted.', 'success')
        else:
            flash('Item not found.', 'error')

        return redirect(url_for('candidate_dashboard'))
