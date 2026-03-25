from datetime import datetime, timedelta

from flask import flash, redirect, render_template, request, url_for

from models import CandidateJobAction, EmployerJob, EmployerProfile, User, db


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

    def employer_dashboard_data(user):
        jobs = EmployerJob.query.filter_by(employer_user_id=user.id).order_by(EmployerJob.created_at.desc()).all()
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
        if redirect_response:
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
        _, redirect_response = ensure_employer_access(require_profile=True)
        if redirect_response:
            return redirect_response
        return render_template('jobposting.html')

    @app.route('/applications.html')
    def employer_applications_page():
        _, redirect_response = ensure_employer_access(require_profile=True)
        if redirect_response:
            return redirect_response
        return render_template('applications.html')

    @app.route('/topcandidate.html')
    def employer_top_candidates_page():
        _, redirect_response = ensure_employer_access(require_profile=True)
        if redirect_response:
            return redirect_response
        return render_template('topcandidate.html')

    @app.route('/massage.html')
    def employer_messages_page():
        _, redirect_response = ensure_employer_access(require_profile=True)
        if redirect_response:
            return redirect_response
        return render_template('massage.html')

    @app.route('/employer/jobs/create', methods=['POST'])
    def create_employer_job():
        user = get_logged_in_user()
        if user is None:
            flash('Please login first.', 'error')
            return redirect(url_for('login'))
        if normalize_role(user.role) != 'employer':
            return redirect(url_for(dashboard_endpoint_for_role(user.role)))

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
            return redirect(url_for('employer_dashboard'))

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

        flash('Job post created successfully.', 'success')
        return redirect(url_for('employer_dashboard'))

    @app.route('/employer/jobs/<int:job_id>/remove', methods=['POST'])
    def remove_employer_job():
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
            password = request.form.get('password', '').strip()

            if not company_name or not hr_name or not email:
                flash('Company name, HR name and email are required.', 'error')
            else:
                email_owner = User.query.filter(User.email == email, User.id != user.id).first()
                if email_owner:
                    flash('This email is already used by another account.', 'error')
                    return render_template(
                        'employerform.html',
                        oauth_data={'name': company_name, 'email': email},
                    )

                if profile is None:
                    profile = EmployerProfile(user_id=user.id)
                profile.company_name = company_name
                profile.hr_name = hr_name
                profile.email = email
                profile.phone = phone
                profile.company_size = company_size
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
        }
        return render_template('employerform.html', oauth_data=oauth_data)
