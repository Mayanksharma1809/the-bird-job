from app import app, db
from skill_test_models import SkillCategory, SkillQuestion

def seed_data():
    with app.app_context():
        # 1. Create categories
        categories_data = [
            {"name": "Python Mastery", "description": "Core concepts, data types, and advanced Python logic.", "emoji": "🐍"},
            {"name": "Frontend (React/JS)", "description": "React lifecycle, hooks, and modern JavaScript ES6+.", "emoji": "⚛️"},
            {"name": "Database & SQL", "description": "Queries, indexing, and normalization patterns.", "emoji": "🗄️"},
            {"name": "Cloud Computing", "description": "AWS, Azure, and infrastructure as code basics.", "emoji": "☁️"}
        ]

        for cat in categories_data:
            if not SkillCategory.query.filter_by(name=cat["name"]).first():
                category = SkillCategory(name=cat["name"], description=cat["description"], icon_emoji=cat["emoji"])
                db.session.add(category)
        
        db.session.commit()

        # 2. Extract IDs
        python_id = SkillCategory.query.filter_by(name="Python Mastery").first().id
        js_id = SkillCategory.query.filter_by(name="Frontend (React/JS)").first().id
        sql_id = SkillCategory.query.filter_by(name="Database & SQL").first().id

        # 3. Add Python Questions
        python_questions = [
            {
                "text": "What is the result of '2' + '2' in Python?",
                "a": "4", "b": "'22'", "c": "TypeError", "d": "None", "correct": "b", "difficulty": "basic"
            },
            {
                "text": "Which of these is used to define a function in Python?",
                "a": "func", "b": "function", "c": "def", "d": "define", "correct": "c", "difficulty": "basic"
            },
            {
                "text": "What is the output of: print(bool([]))?",
                "a": "True", "b": "False", "c": "None", "d": "Error", "correct": "b", "difficulty": "medium"
            }
        ]

        # 4. Add JS Questions
        js_questions = [
            {
                "text": "Which keyword is used to declare a constant in JavaScript?",
                "a": "var", "b": "let", "c": "const", "d": "fixed", "correct": "c", "difficulty": "basic"
            },
            {
                "text": "What does DOM stand for?",
                "a": "Data Object Model", "b": "Document Object Model", "c": "Digital Object Management", "d": "Direct Object Mode", "correct": "b", "difficulty": "basic"
            }
        ]

        # 5. Add SQL Questions
        sql_questions = [
            {
                "text": "Which SQL keyword is used to retrieve data from a database?",
                "a": "GET", "b": "SELECT", "c": "FETCH", "d": "EXTRACT", "correct": "b", "difficulty": "basic"
            },
            {
                "text": "What does the 'JOIN' clause do in SQL?",
                "a": "Combine rows from two or more tables", "b": "Split a table into two", "c": "Add a new column", "d": "Delete duplicate rows", "correct": "a", "difficulty": "basic"
            }
        ]

        def add_questions(cat_id, questions):
            for q in questions:
                if not SkillQuestion.query.filter_by(question_text=q["text"]).first():
                    question = SkillQuestion(
                        category_id=cat_id,
                        question_text=q["text"],
                        option_a=q["a"],
                        option_b=q["b"],
                        option_c=q["c"],
                        option_d=q["d"],
                        correct_option=q["correct"],
                        difficulty=q["difficulty"]
                    )
                    db.session.add(question)

        add_questions(python_id, python_questions)
        add_questions(js_id, js_questions)
        add_questions(sql_id, sql_questions)

        db.session.commit()
        print("Skill Test Database seeded successfully!")

if __name__ == "__main__":
    seed_data()
