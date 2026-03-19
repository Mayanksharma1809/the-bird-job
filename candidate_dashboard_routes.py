from flask import flash, redirect, render_template, request, url_for

from models import CandidateProfile, User, db


def register_candidate_dashboard_routes(app, helpers):
    get_logged_in_user = helpers['get_logged_in_user']
    normalize_role = helpers['normalize_role']
    dashboard_endpoint_for_role = helpers['dashboard_endpoint_for_role']
    first_non_empty = helpers['first_non_empty']
    candidate_dashboard_user = helpers['candidate_dashboard_user']
    has_completed_profile = helpers['has_completed_profile']

    @app.route('/candidate_dashboard')
    def candidate_dashboard():
        user = get_logged_in_user()
        if user is None or normalize_role(user.role) != 'candidate':
            return redirect(url_for('login'))
        if not has_completed_profile(user):
            flash('Please complete your candidate profile first.', 'error')
            return redirect(url_for('candidate_form'))
        return render_template('candidate_dashboard.html', user=candidate_dashboard_user(user))

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
