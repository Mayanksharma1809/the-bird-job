from datetime import datetime, timedelta

from flask import flash, jsonify, redirect, render_template, request, url_for

from models import (
    CandidateJobAction,
    CandidateProfile,
    EmployerJob,
    EmployerProfile,
    Message,
    User,
    db,
)
from ai_helper import analyze_resume_with_backup
from plan_restrictions import (
    DEFAULT_PLAN_TIER,
    can_access_feature,
    can_create_job,
    get_plan_rules,
    normalize_plan_tier,
    plan_label,
)


def register_employer_dashboard_routes(app, helpers):
    get_logged_in_user = helpers['get_logged_in_user']
    normalize_role = helpers['normalize_role']
    dashboard_endpoint_for_role = helpers['dashboard_endpoint_for_role']
    first_non_empty = helpers['first_non_empty']
    employer_dashboard_user = helpers['employer_dashboard_user']
    has_completed_profile = helpers['has_completed_profile']

    def parse_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def split_skills(value):
        if not value:
            return []
        return [item.strip() for item in str(value).split(',') if item.strip()]

    def employer_plan_tier(user):
        profile = EmployerProfile.query.filter_by(user_id=user.id).first()
        configured_default = normalize_plan_tier(app.config.get('EMPLOYER_DEFAULT_PLAN_TIER', DEFAULT_PLAN_TIER))
        if profile is None:
            return configured_default
        return normalize_plan_tier(profile.plan_tier, default=configured_default)

    def normalize_application_status(value):
        raw = (value or '').strip().lower()
        mapping = {
            'new': 'new',
            'submitted': 'new',
            'shortlist': 'shortlisted',
            'shortlisted': 'shortlisted',
            'review': 'shortlisted',
            'interview': 'interviewed',
            'interviewed': 'interviewed',
            'hired': 'hired',
            'reject': 'rejected',
            'rejected': 'rejected',
        }
        return mapping.get(raw, 'new')

    def employer_applications_data(user):
        jobs = EmployerJob.query.filter(
            EmployerJob.employer_user_id == user.id,
            EmployerJob.status != 'removed'
        ).all()
        job_by_id = {job.id: job for job in jobs}
        job_ids = list(job_by_id.keys())
        if not job_ids:
            return [], {
                'total': 0,
                'submitted': 0,
                'shortlisted': 0,
                'interview': 0,
                'hired': 0,
                'rejected': 0,
            }

        records = (
            CandidateJobAction.query
            .filter(
                CandidateJobAction.employer_job_id.in_(job_ids),
                CandidateJobAction.action == 'applied',
            )
            .order_by(CandidateJobAction.created_at.desc())
            .all()
        )

        status_counts = {
            'total': len(records),
            'submitted': 0,
            'shortlisted': 0,
            'interview': 0,
            'hired': 0,
            'rejected': 0,
        }
        items = []

        for record in records:
            normalized_status = normalize_application_status(record.status)
            if normalized_status in status_counts:
                status_counts[normalized_status] += 1

            job = job_by_id.get(record.employer_job_id)
            candidate_user = record.candidate
            candidate_profile = candidate_user.candidate_profile if candidate_user else None
            candidate_name = first_non_empty(
                [
                    candidate_profile.name if candidate_profile else '',
                    candidate_user.full_name if candidate_user else '',
                    candidate_user.username if candidate_user else '',
                ],
                fallback='Candidate',
            )
            candidate_email = first_non_empty(
                [
                    candidate_profile.email if candidate_profile else '',
                    candidate_user.email if candidate_user else '',
                ],
                fallback='Not shared',
            )

            items.append(
                {
                    'id': record.id,
                    'job_id': record.employer_job_id,
                    'job_title': first_non_empty([record.job_title, job.title if job else ''], fallback='Untitled role'),
                    'job_location': first_non_empty([getattr(candidate_profile, 'location', ''), record.location], fallback='Location not specified'),
                    'candidate_user_id': candidate_user.id if candidate_user else None,
                    'candidate_name': candidate_name,
                    'candidate_email': candidate_email,
                    'candidate_skills': split_skills(candidate_profile.skills if candidate_profile else ''),
                    'candidate_experience': first_non_empty(
                        [candidate_profile.experience if candidate_profile else ''],
                        fallback='Not provided',
                    ),
                    'candidate_resume': getattr(candidate_profile, 'resume_text', '') or candidate_profile.experience if candidate_profile else '',
                    'applied_at': record.created_at,
                    'status': normalized_status,
                    'raw_status': record.status,
                    'required_skills': split_skills(job.required_skills if job else ''),
                    'job_description': job.description if job else '',
                }
            )

        return items, status_counts

    def score_candidate(application):
        resume_text = application.get('candidate_resume', '')
        if not resume_text:
            skills = application.get('candidate_skills') or []
            resume_text = "Skills: " + ", ".join(skills)
            
        job_desc = application.get('job_description', '')
        if not job_desc:
            job_desc = "Required Skills: " + ", ".join(application.get('required_skills') or [])
            
        analysis, _provider, _fallback = analyze_resume_with_backup(resume_text, job_desc)
        skills_score = float(analysis.get('score', 72)) if isinstance(analysis, dict) else 72.0

        status_bonus = {
            'new': 0,
            'shortlisted': 12,
            'interviewed': 16,
            'hired': 20,
            'rejected': -12,
        }.get(application.get('status'), 0)

        applied_at = application.get('applied_at')
        if applied_at:
            days_old = max((datetime.utcnow() - applied_at).days, 0)
            recency_bonus = max(0, 12 - min(days_old, 12))
        else:
            recency_bonus = 0

        final_score_raw = int((skills_score * 0.78) + status_bonus + recency_bonus)
        final_score = max(35, min(99, final_score_raw))
        return final_score

    def top_candidates_data(user):
        applications, _ = employer_applications_data(user)
        ranked = []
        for row in applications:
            ranked.append(
                {
                    **row,
                    'match_score': score_candidate(row),
                }
            )

        ranked.sort(key=lambda item: (item['match_score'], item['applied_at'] or datetime.min), reverse=True)
        return ranked

    def messages_conversations_data(user):
        # Get all distinct users I have talked to
        sent_to = [r[0] for r in db.session.query(Message.receiver_id).filter_by(sender_id=user.id).all()]
        received_from = [r[0] for r in db.session.query(Message.sender_id).filter_by(receiver_id=user.id).all()]

        # Also get candidates who applied to my jobs
        jobs = EmployerJob.query.filter_by(employer_user_id=user.id).all()
        job_ids = [j.id for j in jobs]
        applicants = [r[0] for r in db.session.query(CandidateJobAction.candidate_user_id).filter(
            CandidateJobAction.employer_job_id.in_(job_ids),
            CandidateJobAction.action == 'applied'
        ).all()]

        participant_ids = list(set(sent_to + received_from + applicants))

        conversations = []
        for p_id in participant_ids:
            if not p_id: continue
            participant = User.query.get(p_id)
            if not participant:
                continue

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

            profile = participant.candidate_profile
            
            # Find the most recent job they applied to for the role description
            latest_app = CandidateJobAction.query.filter_by(
                candidate_user_id=p_id, action='applied'
            ).filter(CandidateJobAction.employer_job_id.in_(job_ids)).order_by(CandidateJobAction.created_at.desc()).first()

            role_desc = latest_app.job_title if latest_app else (latest_app.employer_job.title if latest_app and latest_app.employer_job else "Candidate")

            conversations.append(
                {
                    'id': participant.id,
                    'name': profile.name if profile else (participant.full_name or participant.username),
                    'role': role_desc,
                    'last_message': last_msg.content if last_msg else 'No messages yet.',
                    'last_time': last_msg.timestamp.isoformat() if last_msg else (latest_app.created_at.isoformat() if latest_app else ''),
                    'unread_count': unread_count,
                    'initials': (
                        profile.name if profile else (participant.full_name or participant.username or '??')
                    )[:2].upper(),
                }
            )

        # Sort by last activity (message time or application time)
        conversations.sort(key=lambda x: x['last_time'], reverse=True)
        return conversations

    def employer_dashboard_data(user):
        jobs = EmployerJob.query.filter(
            EmployerJob.employer_user_id == user.id,
            EmployerJob.status != 'removed'
        ).order_by(EmployerJob.created_at.desc()).all()
        job_ids = [job.id for job in jobs]

        if job_ids:
            applied_query = CandidateJobAction.query.filter(
                CandidateJobAction.employer_job_id.in_(job_ids),
                CandidateJobAction.action == 'applied',
            )
            total_applications = applied_query.count()
            interviews_scheduled = applied_query.filter(CandidateJobAction.status == 'interview').count()

            month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            hires_this_month = applied_query.filter(
                CandidateJobAction.status == 'hired',
                CandidateJobAction.updated_at >= month_start,
            ).count()
            recent_applications = applied_query.order_by(CandidateJobAction.created_at.desc()).limit(10).all()
        else:
            total_applications = 0
            interviews_scheduled = 0
            hires_this_month = 0
            recent_applications = []

        active_jobs = sum(1 for job in jobs if (job.status or '').lower() == 'active')
        stats = {
            'total_applications': total_applications,
            'active_jobs': active_jobs,
            'interviews_scheduled': interviews_scheduled,
            'hires_this_month': hires_this_month,
        }
        return jobs, stats, recent_applications

    def ensure_employer_access(require_profile=True):
        user = get_logged_in_user()
        if user is None:
            flash('Please login first.', 'error')
            return None, redirect(url_for('login'))
        if normalize_role(user.role) != 'employer':
            return None, redirect(url_for(dashboard_endpoint_for_role(user.role)))
        if require_profile and not has_completed_profile(user):
            flash('Please complete your employer profile first.', 'error')
            return None, redirect(url_for('employer_form'))
        return user, None

    @app.route('/employer_dashboard')
    def employer_dashboard():
        user, redirect_response = ensure_employer_access(require_profile=True)
        if user is None:
            return redirect_response
        jobs, stats, recent_applications = employer_dashboard_data(user)
        dashboard_user = employer_dashboard_user(user)
        dashboard_user['jobs'] = jobs
        dashboard_user['stats'] = stats
        candidate_visibility_days = 30
        try:
            candidate_visibility_days = int(app.config.get('EMPLOYER_JOB_VISIBILITY_DAYS', 30))
        except (TypeError, ValueError):
            candidate_visibility_days = 30
        candidate_visibility_days = max(candidate_visibility_days, 1)
        visibility_cutoff = datetime.utcnow() - timedelta(days=candidate_visibility_days)

        return render_template(
            'employer_dashboard.html',
            user=dashboard_user,
            candidate_applications=recent_applications,
            candidate_visibility_days=candidate_visibility_days,
            visibility_cutoff=visibility_cutoff,
            now_utc=datetime.utcnow(),
        )

    @app.route('/jobposting.html')
    def employer_jobposting_page():
        user, redirect_response = ensure_employer_access(require_profile=True)
        if user is None:
            return redirect_response
        plan_tier = employer_plan_tier(user)
        plan_rules = get_plan_rules(plan_tier)
        
        active_jobs_count = EmployerJob.query.filter_by(employer_user_id=user.id, status='active').count()
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        posted_this_month_count = EmployerJob.query.filter(
            EmployerJob.employer_user_id == user.id,
            EmployerJob.created_at >= month_start
        ).count()
        
        allowed, reason = can_create_job(plan_tier, active_jobs_count, posted_this_month_count)
        if not allowed:
            flash(reason, 'info')
            return redirect(url_for('employer_pricing_page'))

        return render_template(
            'jobposting.html',
            user=employer_dashboard_user(user),
            plan_tier=plan_tier,
            plan_label=plan_label(plan_tier),
            plan_rules=plan_rules,
            active_jobs_count=active_jobs_count,
        )

    @app.route('/applications.html')
    def employer_applications_page():
        user, redirect_response = ensure_employer_access(require_profile=True)
        if user is None:
            return redirect_response
        applications, status_counts = employer_applications_data(user)
        jobs = EmployerJob.query.filter(
            EmployerJob.employer_user_id == user.id,
            EmployerJob.status != 'removed'
        ).all()
        return render_template(
            'applications.html',
            user=employer_dashboard_user(user),
            applications=applications,
            status_counts=status_counts,
            jobs=jobs,
        )

    @app.route('/topcandidate.html')
    def employer_top_candidates_page():
        user, redirect_response = ensure_employer_access(require_profile=True)
        if user is None:
            return redirect_response
        plan_tier = employer_plan_tier(user)
        if not can_access_feature(plan_tier, 'can_view_top_candidates'):
            flash(f'Your {plan_label(plan_tier)} plan does not include Top Candidates.', 'error')
            return redirect(url_for('employer_dashboard'))

        ranked_candidates = top_candidates_data(user)
        return render_template(
            'topcandidate.html',
            user=employer_dashboard_user(user),
            candidates=ranked_candidates,
            plan_tier=plan_tier,
            plan_label=plan_label(plan_tier),
        )

    @app.route('/massage.html')
    def employer_messages_page():
        user, redirect_response = ensure_employer_access(require_profile=True)
        if user is None:
            return redirect_response
        
        plan_tier = employer_plan_tier(user)
        if not can_access_feature(plan_tier, 'can_use_messages'):
            flash(f'Your {plan_label(plan_tier)} plan does not include employer messaging.', 'error')
            return redirect(url_for('employer_dashboard'))

        conversations = messages_conversations_data(user)
        return render_template(
            'massage.html',
            user=employer_dashboard_user(user),
            conversations=conversations,
            plan_tier=plan_tier,
            plan_label=plan_label(plan_tier),
        )

    @app.route('/api/employer/conversations')
    def get_employer_conversations_api():
        user = get_logged_in_user()
        if not user or normalize_role(user.role) != 'employer':
            return jsonify([]), 401
        
        conversations = messages_conversations_data(user)
        return jsonify(conversations)

    @app.route('/api/employer/messages/<int:candidate_id>')
    def get_chat_messages(candidate_id):
        user = get_logged_in_user()
        if not user or normalize_role(user.role) != 'employer':
            return jsonify([]), 401

        messages = (
            Message.query.filter(
                ((Message.sender_id == user.id) & (Message.receiver_id == candidate_id)) |
                ((Message.sender_id == candidate_id) & (Message.receiver_id == user.id))
            )
            .order_by(Message.timestamp.asc())
            .all()
        )

        # Mark received messages from this candidate as read
        Message.query.filter_by(
            sender_id=candidate_id, receiver_id=user.id, is_read=False
        ).update({'is_read': True})
        db.session.commit()

        return jsonify(
            [
                {
                    'id': m.id,
                    'sender_id': m.sender_id,
                    'content': m.content,
                    'timestamp': m.timestamp.isoformat(),
                    'mine': m.sender_id == user.id,
                }
                for m in messages
            ]
        )

    @app.route('/api/employer/messages/send', methods=['POST'])
    def send_employer_message():
        user = get_logged_in_user()
        if not user or normalize_role(user.role) != 'employer':
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json or {}
        candidate_id = data.get('candidate_id')
        content = data.get('content')

        if not candidate_id or not content:
            return jsonify({'error': 'Invalid data'}), 400

        msg = Message(sender_id=user.id, receiver_id=candidate_id, content=content)
        db.session.add(msg)
        db.session.commit()

        return jsonify(
            {
                'id': msg.id,
                'sender_id': msg.sender_id,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'mine': True,
            }
        )

    @app.route('/employer/jobs/create', methods=['POST'])
    def create_employer_job():
        user, redirect_response = ensure_employer_access(require_profile=True)
        if user is None:
            return redirect_response

        title = request.form.get('title', '').strip()
        location = request.form.get('location', '').strip()
        job_type = request.form.get('job_type', '').strip()
        salary = request.form.get('salary', '').strip()
        experience_level = request.form.get('experience_level', '').strip()
        min_ats_score = parse_int(request.form.get('min_ats_score', '').strip())
        required_skills = request.form.get('required_skills', '').strip()
        description = request.form.get('description', '').strip()

        if not title or not description:
            flash('Job title and description are required.', 'error')
            return redirect(url_for('employer_jobposting_page'))

        active_jobs_count = EmployerJob.query.filter_by(employer_user_id=user.id, status='active').count()
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        posted_this_month_count = (
            EmployerJob.query
            .filter(
                EmployerJob.employer_user_id == user.id,
                EmployerJob.created_at >= month_start,
            )
            .count()
        )
        plan_tier = employer_plan_tier(user)
        allowed, reason = can_create_job(plan_tier, active_jobs_count, posted_this_month_count)
        if not allowed:
            flash(reason, 'error')
            return redirect(url_for('employer_pricing_page'))

        new_job = EmployerJob(
            employer_user_id=user.id,
            title=title,
            location=location or None,
            job_type=job_type or None,
            salary=salary or None,
            experience_level=experience_level or None,
            min_ats_score=min_ats_score,
            required_skills=required_skills or None,
            description=description,
            status='active',
        )

        try:
            db.session.add(new_job)
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception('Failed to create employer job')
            flash('Unable to create the job post right now. Please try again.', 'error')
            return redirect(url_for('employer_dashboard'))

        flash('Job post created successfully. It is now visible in My Jobs and candidate job feed.', 'success')
        return redirect(url_for('employer_dashboard'))

    @app.route('/employer/applications/<int:application_id>/status', methods=['POST'])
    def update_employer_application_status(application_id):
        user, redirect_response = ensure_employer_access(require_profile=True)
        if user is None:
            return redirect_response

        application = CandidateJobAction.query.filter_by(id=application_id, action='applied').first()
        if application is None or application.employer_job is None or application.employer_job.employer_user_id != user.id:
            flash('Application not found.', 'error')
            return redirect(url_for('employer_applications_page'))

        new_status = normalize_application_status(request.form.get('status'))
        try:
            application.status = new_status
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception('Failed to update candidate application status')
            flash('Unable to update status right now. Please try again.', 'error')
            return redirect(url_for('employer_applications_page'))

        flash('Application status updated.', 'success')
        return redirect(url_for('employer_applications_page'))

    @app.route('/employer/jobs/<int:job_id>/remove', methods=['POST'])
    def remove_employer_job(job_id):
        user = get_logged_in_user()
        if user is None:
            flash('Please login first.', 'error')
            return redirect(url_for('login'))
        if normalize_role(user.role) != 'employer':
            return redirect(url_for(dashboard_endpoint_for_role(user.role)))

        job = EmployerJob.query.filter_by(id=job_id, employer_user_id=user.id).first()
        if job is None:
            flash('Job post not found.', 'error')
            return redirect(url_for('employer_dashboard'))

        if (job.status or '').lower() != 'active':
            flash('This job is already removed from candidate visibility.', 'success')
            return redirect(url_for('employer_dashboard'))

        try:
            job.status = 'removed'
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception('Failed to remove employer job from candidate visibility')
            flash('Unable to remove the job right now. Please try again.', 'error')
            return redirect(url_for('employer_dashboard'))

        flash('Job removed from candidate dashboard visibility.', 'success')
        return redirect(url_for('employer_dashboard'))

    @app.route('/employer_form', methods=['GET', 'POST'])
    def employer_form():
        user = get_logged_in_user()
        if user is None:
            flash('Please login first.', 'error')
            return redirect(url_for('login'))
        if normalize_role(user.role) != 'employer':
            return redirect(url_for(dashboard_endpoint_for_role(user.role)))

        profile = EmployerProfile.query.filter_by(user_id=user.id).first()
        if request.method == 'POST':
            company_name = first_non_empty(request.form.getlist('company_name'))
            hr_name = request.form.get('hr_name', '').strip()
            primary_email = request.form.get('email', '').strip().lower()
            account_email = request.form.get('account_email', '').strip().lower()
            email = first_non_empty([account_email, primary_email]).lower()
            phone = request.form.get('phone', '').strip()
            company_size = request.form.get('company_size', '').strip()
            plan_tier = normalize_plan_tier(request.form.get('plan_tier'), normalize_plan_tier(app.config.get('EMPLOYER_DEFAULT_PLAN_TIER', DEFAULT_PLAN_TIER)))
            password = request.form.get('password', '').strip()

            if not company_name or not hr_name or not email:
                flash('Company name, HR name and email are required.', 'error')
            else:
                email_owner = User.query.filter(User.email == email, User.id != user.id).first()
                if email_owner:
                    flash('This email is already used by another account.', 'error')
                    return render_template(
                        'employerform.html',
                        oauth_data={
                            'name': company_name,
                            'email': email,
                            'company_size': company_size,
                            'plan_tier': plan_tier,
                        },
                    )

                if profile is None:
                    profile = EmployerProfile(user_id=user.id)
                profile.company_name = company_name
                profile.hr_name = hr_name
                profile.email = email
                profile.phone = phone
                profile.company_size = company_size
                profile.plan_tier = plan_tier
                user.email = email
                user.full_name = hr_name
                if password:
                    user.password = password
                db.session.add(profile)
                db.session.commit()
                flash('Employer profile saved successfully.', 'success')
                return redirect(url_for('employer_dashboard'))

        oauth_data = {
            'name': profile.company_name if profile else (user.full_name or ''),
            'email': profile.email if profile else user.email,
            'company_size': profile.company_size if profile else '',
            'plan_tier': normalize_plan_tier(
                profile.plan_tier if profile else app.config.get('EMPLOYER_DEFAULT_PLAN_TIER', DEFAULT_PLAN_TIER)
            ),
        }
        return render_template('employerform.html', oauth_data=oauth_data)

    @app.route('/employer/pricing')
    def employer_pricing_page():
        user, redirect_response = ensure_employer_access(require_profile=True)
        if user is None:
            return redirect_response
        return render_template(
            'employer_pricing.html',
            user=employer_dashboard_user(user),
            plan_tier=employer_plan_tier(user),
            plan_label=plan_label(employer_plan_tier(user)),
        )
