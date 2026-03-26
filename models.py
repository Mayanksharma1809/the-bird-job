from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, index=True)  # 'candidate' or 'employer'
    auth_provider = db.Column(db.String(30), nullable=True, default='local')
    google_sub = db.Column(db.String(255), unique=True, nullable=True)
    full_name = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    candidate_profile = db.relationship(
        'CandidateProfile',
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan',
    )
    employer_profile = db.relationship(
        'EmployerProfile',
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan',
    )
    login_events = db.relationship(
        'LoginEvent',
        back_populates='user',
        cascade='all, delete-orphan',
    )
    employer_jobs = db.relationship(
        'EmployerJob',
        back_populates='employer',
        cascade='all, delete-orphan',
    )
    candidate_job_actions = db.relationship(
        'CandidateJobAction',
        back_populates='candidate',
        cascade='all, delete-orphan',
    )
    sent_messages = db.relationship(
        'Message',
        foreign_keys='Message.sender_id',
        back_populates='sender',
        cascade='all, delete-orphan',
    )
    received_messages = db.relationship(
        'Message',
        foreign_keys='Message.receiver_id',
        back_populates='receiver',
        cascade='all, delete-orphan',
    )


class EmployerJob(db.Model):
    __tablename__ = 'employer_jobs'

    id = db.Column(db.Integer, primary_key=True)
    employer_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(160), nullable=True)
    job_type = db.Column(db.String(60), nullable=True)
    salary = db.Column(db.String(120), nullable=True)
    experience_level = db.Column(db.String(120), nullable=True)
    min_ats_score = db.Column(db.Integer, nullable=True)
    required_skills = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default='active', index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    employer = db.relationship('User', back_populates='employer_jobs')
    applications = db.relationship(
        'CandidateJobAction',
        back_populates='employer_job',
        cascade='all, delete-orphan',
    )


class CandidateJobAction(db.Model):
    __tablename__ = 'candidate_job_actions'

    id = db.Column(db.Integer, primary_key=True)
    candidate_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    employer_job_id = db.Column(db.Integer, db.ForeignKey('employer_jobs.id', ondelete='SET NULL'), nullable=True, index=True)
    source = db.Column(db.String(30), nullable=False, default='api')
    external_job_id = db.Column(db.String(255), nullable=True, index=True)
    job_title = db.Column(db.String(200), nullable=False)
    company_name = db.Column(db.String(200), nullable=True)
    location = db.Column(db.String(160), nullable=True)
    salary = db.Column(db.String(120), nullable=True)
    job_url = db.Column(db.String(500), nullable=True)
    action = db.Column(db.String(20), nullable=False, default='applied')  # applied/saved
    status = db.Column(db.String(20), nullable=False, default='submitted')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    candidate = db.relationship('User', back_populates='candidate_job_actions')
    employer_job = db.relationship('EmployerJob', back_populates='applications')


class CandidateProfile(db.Model):
    __tablename__ = 'candidate_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(40), nullable=True)
    skills = db.Column(db.Text, nullable=True)
    experience = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', back_populates='candidate_profile')


class EmployerProfile(db.Model):
    __tablename__ = 'employer_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    company_name = db.Column(db.String(255), nullable=False)
    hr_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(40), nullable=True)
    company_size = db.Column(db.String(120), nullable=True)
    plan_tier = db.Column(db.String(30), nullable=False, default='starter')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', back_populates='employer_profile')


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    is_read = db.Column(db.Boolean, default=False)

    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], back_populates='received_messages')


class LoginEvent(db.Model):
    __tablename__ = 'login_events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    provider = db.Column(db.String(30), nullable=False)  # local/google
    role_snapshot = db.Column(db.String(50), nullable=False)
    is_new_user = db.Column(db.Boolean, nullable=False, default=False)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', back_populates='login_events')
