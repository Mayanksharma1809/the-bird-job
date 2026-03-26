from datetime import datetime
from models import db

class SkillCategory(db.Model):
    __tablename__ = 'skill_categories'
    __bind_key__ = 'skill_test'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    icon_emoji = db.Column(db.String(20), nullable=True, default='🧠')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship('SkillQuestion', backref='category', lazy=True, cascade='all, delete-orphan')

class SkillQuestion(db.Model):
    __tablename__ = 'skill_questions'
    __bind_key__ = 'skill_test'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('skill_categories.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False) # 'a', 'b', 'c', 'd'
    difficulty = db.Column(db.String(20), default='medium')

class CandidateSkillScore(db.Model):
    __tablename__ = 'candidate_skill_scores'
    __bind_key__ = 'skill_test'
    id = db.Column(db.Integer, primary_key=True)
    # Note: No hard ForeignKey to 'users.id' because 'users' is in a different database
    user_id = db.Column(db.Integer, nullable=False, index=True)
    category_name = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
