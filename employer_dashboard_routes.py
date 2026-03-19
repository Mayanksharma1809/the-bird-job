from flask import flash, redirect, render_template, request, url_for

from models import EmployerProfile, User, db


def register_employer_dashboard_routes(app, helpers):
    get_logged_in_user = helpers['get_logged_in_user']
    normalize_role = helpers['normalize_role']
    dashboard_endpoint_for_role = helpers['dashboard_endpoint_for_role']
    first_non_empty = helpers['first_non_empty']
    employer_dashboard_user = helpers['employer_dashboard_user']
    has_completed_profile = helpers['has_completed_profile']

    @app.route('/employer_dashboard')
    def employer_dashboard():
        user = get_logged_in_user()
        if user is None or normalize_role(user.role) != 'employer':
            return redirect(url_for('login'))
        if not has_completed_profile(user):
            flash('Please complete your employer profile first.', 'error')
            return redirect(url_for('employer_form'))
        return render_template('employer_dashboard.html', user=employer_dashboard_user(user))

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
