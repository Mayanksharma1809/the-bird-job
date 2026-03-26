from flask import Blueprint, render_template, request, session, jsonify, flash, redirect, url_for
from models import db
from skill_test_models import SkillCategory, SkillQuestion, CandidateSkillScore
import json

skill_test_bp = Blueprint('skill_test', __name__)

@skill_test_bp.route('/skill_test')
def list_categories():
    """Shows all available skill categories."""
    categories = SkillCategory.query.all()
    # If no categories exist, we'll suggest creating some
    return render_template('skill_test_list.html', categories=categories)

@skill_test_bp.route('/skill_test/<category_name>')
def take_skill_test(category_name):
    """Renders the test environment for a specific category."""
    category = SkillCategory.query.filter_by(name=category_name).first()
    if not category:
        flash(f'Skill test for "{category_name}" is not available yet.', 'error')
        return redirect(url_for('skill_test.list_categories'))
    
    return render_template('skill_test.html', category=category)

@skill_test_bp.route('/api/skill_test/<int:category_id>/questions')
def get_questions(category_id):
    """API: returns JSON questions for a test."""
    questions = SkillQuestion.query.filter_by(category_id=category_id).all()
    output = []
    for q in questions:
        output.append({
            'id': q.id,
            'question': q.question_text,
            'options': {
                'a': q.option_a,
                'b': q.option_b,
                'c': q.option_c,
                'd': q.option_d
            }
        })
    return jsonify({'questions': output})

@skill_test_bp.route('/api/skill_test/submit', methods=['POST'])
def submit_score():
    """API: records a candidate's score."""
    if 'user_id' not in session or session.get('role') != 'candidate':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    category_id = data.get('category_id')
    score = data.get('score')
    total = data.get('total')
    
    category = SkillCategory.query.get(category_id)
    if not category:
        return jsonify({'error': 'Category not found'}), 404
    
    new_score = CandidateSkillScore(
        user_id=session['user_id'],
        category_name=category.name,
        score=score,
        total_questions=total
    )
    db.session.add(new_score)
    db.session.commit()
    
    return jsonify({'success': True, 'score': score, 'total': total})
