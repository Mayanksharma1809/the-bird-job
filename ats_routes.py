# ============================================================
#  ATS SCANNER BACKEND — ats_routes.py  (FINAL FIXED)
#  Gemini 2.5 Flash Lite → PDF text extract ONLY
#  Groq llama-3.3-70b   → ATS Scoring + Rewrite
#  thebirdjob.in
# ============================================================

from flask import Blueprint, request, jsonify, session, redirect, url_for
from models import db, PortfolioItem, User
import os, re, json, base64

def get_logged_in_user():
    user_id = session.get('user_id')
    if not user_id: return None
    return db.session.get(User, user_id)

def ensure_candidate_access():
    user = get_logged_in_user()
    if not user: return None, redirect(url_for('login'))
    role = (user.role or '').strip().lower()
    if role not in ('candidate', 'jobseeker', 'job_seeker', 'seeker'):
        return None, redirect(url_for('candidate_dashboard'))
    return user, None
import pdfplumber
from docx import Document
from groq import Groq
import google.generativeai as genai

ats_bp = Blueprint('ats', __name__)

GROQ_API_KEY_1 = os.environ.get("GROQ_API_KEY_1", "")
GROQ_API_KEY_2 = os.environ.get("GROQ_API_KEY_2", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "your-gemini-api-key")

groq_score_client   = Groq(api_key=GROQ_API_KEY_1)
groq_rewrite_client = Groq(api_key=GROQ_API_KEY_2)
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite")


# ============================================================
# STEP 1 — Gemini se PDF ka clean text nikalo
# Sirf extraction — koi scoring nahi
# ============================================================
def extract_text_gemini(file) -> str:
    filename = file.filename.lower()

    if filename.endswith('.pdf'):
        file.seek(0)
        pdf_bytes  = file.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

        response = gemini_model.generate_content([
            {
                "inline_data": {
                    "mime_type": "application/pdf",
                    "data":      pdf_base64
                }
            },
            """Extract ALL text from this PDF resume exactly as it appears.
Keep all sections, skills, experience, education intact.
Return ONLY the plain text — no formatting, no markdown, no explanation.
Just the raw resume text."""
        ])
        return response.text or ""

    elif filename.endswith('.docx'):
        file.seek(0)
        doc = Document(file)
        return "\n".join(p.text for p in doc.paragraphs)

    elif filename.endswith('.txt'):
        file.seek(0)
        return file.read().decode('utf-8', errors='ignore')

    else:
        file.seek(0)
        try:
            with pdfplumber.open(file) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except:
            return ""


# ============================================================
# STEP 2 — Groq se ATS score lo
# ============================================================
def score_with_groq(resume_text: str, jd_text: str) -> dict:

    prompt = f"""You are an expert ATS analyst. Score this resume against the job description.

RESUME:
{resume_text[:3000]}

JOB DESCRIPTION:
{jd_text[:2000]}

Score using EXACTLY this formula:

1. keyword_match (35% weight):
   - Extract meaningful keywords from JD
   - Check how many are in resume (semantic match allowed)
   - MySQL = SQL, PostgreSQL = SQL, ReactJS = React, NodeJS = Node
   - Score = (found / total) * 100

2. skills_match (25% weight):
   - Required skills from JD vs resume skills
   - Semantic match allowed
   - Score = (matched / required) * 100

3. experience_match (20% weight):
   - JD says "0-2 years" or "freshers welcome" → score 65
   - Strong projects but no work exp → score 55-65
   - Meets required years → 90
   - 1 year less → 70
   - 2+ years less → 40
   - No info → 45

4. education_match (10% weight):
   - Exact degree + field → 90-95
   - Related degree → 70-80
   - Different field → 55-65
   - Not mentioned → 40

5. formatting (10% weight):
   - Has Skills section → +17
   - Has Experience/Projects section → +17
   - Has Education section → +17
   - Has contact info → +17
   - Has Summary/Objective → +16
   - Proper length → +16

overall = (keyword*0.35) + (skills*0.25) + (experience*0.20) + (education*0.10) + (formatting*0.10)

Return ONLY this JSON — no markdown, no explanation:
{{
  "overall_score": <number>,
  "rule_scores": {{
    "keyword_match":    <number>,
    "skills_match":     <number>,
    "experience_match": <number>,
    "education_match":  <number>,
    "formatting":       <number>
  }},
  "present_keywords": ["max 10 JD keywords found in resume"],
  "missing_keywords": ["max 8 important JD keywords NOT in resume"],
  "strengths": [
    "Strength 1 in Hinglish",
    "Strength 2 in Hinglish",
    "Strength 3 in Hinglish"
  ],
  "issues": [
    "Issue 1 — exact keyword jo add karna hai",
    "Issue 2 — specific fix",
    "Issue 3 — specific fix",
    "Issue 4 — specific fix"
  ],
  "source_note": "One sentence summary in Hinglish"
}}"""

    completion = groq_score_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        max_tokens=2000,
        messages=[
            {
                "role":    "system",
                "content": "You are an ATS scoring expert. Always respond with valid JSON only. No markdown. No extra text."
            },
            {
                "role":    "user",
                "content": prompt
            }
        ]
    )

    raw   = completion.choices[0].message.content or ""
    clean = re.sub(r'```json|```', '', raw).strip()
    return json.loads(clean)


# ============================================================
# HELPER — Rewrite ke liye missing keywords
# ============================================================
def get_missing_keywords(resume_text: str, jd_text: str) -> list:
    resume_lower = resume_text.lower()
    stopwords = {
        'the','and','for','are','with','this','that','have','from',
        'will','you','your','our','their','they','been','also','its',
        'not','but','was','all','any','can','per','may','must','role',
        'able','both','each','such','into','over','than','then','when',
        'who','which','what','how','where','very','well','good','work',
        'team','join','new','get','set','use','make','help','high',
        'manage','managed','support','ensure','provide','maintain',
        'develop','assist','handle','review','prepare','conduct',
        'implement','coordinate','process','perform','responsible',
        'including','related','required','strong','excellent',
        'proactive','detail','oriented','seeking','looking','ideal',
        'candidate','company','please','apply','about','other',
        'day','full','cycle','primary','point','contact','accurate',
        'regularly','resolve','boost','organize','morale','retention',
        'compliant','national','local','typical','proven','depth',
        'broad','entry','level','clerical','trained','specific','lead',
        'building','robust','scalable','performance','server','side',
        'writing','efficient','utilizing','conducting','ensuring',
        'quality','cross','functional','define','deliver','deep',
        'understanding','hands','proficiency','familiarity','basics',
        'preferred','between','servers','users','tasks','operational',
        'workflows','pipelines','datasets','troubleshooting','free',
        'stakeholders','requirements','solutions','clean','maintainable'
    }
    jd_words    = re.findall(r'\b[a-zA-Z][a-zA-Z+#./\-]{2,}\b', jd_text)
    jd_keywords = list({
        w.lower() for w in jd_words
        if w.lower() not in stopwords and len(w) >= 3
    })
    missing = [kw for kw in jd_keywords if kw not in resume_lower]
    return missing[:20]


# ============================================================
# SCAN ENDPOINT — /candidate/ats/scan
# ============================================================
@ats_bp.route('/candidate/ats/scan', methods=['POST'])
def ats_scan():
    try:
        resume_file = request.files.get('resume')
        if not resume_file:
            return jsonify({"error": "Resume file required"}), 400

        jd_text = request.form.get('job_description', '').strip()
        jd_file = request.files.get('job_description_file')
        if jd_file and not jd_text:
            jd_text = extract_text_gemini(jd_file)

        if not jd_text or len(jd_text.strip()) < 30:
            return jsonify({"error": "Job description required hai"}), 400

        # Step 1 — Gemini se text nikalo
        resume_text = extract_text_gemini(resume_file)

        if not resume_text or len(resume_text.strip()) < 50:
            return jsonify({"error": "Resume text extract nahi hua."}), 400

        # Step 2 — Groq se score
        result      = score_with_groq(resume_text, jd_text)
        rule_scores = result.get("rule_scores", {})
        overall     = result.get("overall_score", 0)

        return jsonify({
            "score":                overall,
            "rule_scores":          rule_scores,
            "resume_text":          resume_text[:500],
            "job_description_text": jd_text[:200],
            "present_keywords":     result.get("present_keywords", []),
            "missing_keywords":     result.get("missing_keywords", []),
            "strengths":            result.get("strengths", []),
            "issues":               result.get("issues", []),
            "source_note":          result.get("source_note", ""),
            "feedback": (
                ["✅ " + s for s in result.get("strengths", [])] +
                ["❌ " + i for i in result.get("issues",    [])]
            )
        })

    except Exception as e:
        print(f"ATS scan error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================
# REWRITE ENDPOINT — /ats/rewrite
# ============================================================
@ats_bp.route('/ats/rewrite', methods=['POST'])
def ats_rewrite():
    try:
        resume_file = request.files.get('resume')
        jd_text     = request.form.get('job_description', '').strip()

        if not resume_file:
            return jsonify({"error": "Resume file required"}), 400

        resume_text = extract_text_gemini(resume_file)

        if not resume_text or len(resume_text.strip()) < 50:
            return jsonify({"error": "Resume text extract nahi hua."}), 400

        missing_keywords = get_missing_keywords(resume_text, jd_text)
        missing_str      = ', '.join(missing_keywords) if missing_keywords else "None"

        rewrite_prompt = f"""You are an expert ATS resume writer.

ORIGINAL RESUME:
{resume_text[:3000]}

JOB DESCRIPTION:
{jd_text[:1500]}

MISSING KEYWORDS TO ADD:
{missing_str}

Write the resume in EXACTLY this format:

[CANDIDATE NAME]
Email: [email] | Phone: [phone] | LinkedIn: [url] | GitHub: [url]

SUMMARY
Write 2-3 lines here as plain sentences.

SKILLS
- Skill1, Skill2, Skill3, Skill4
- Skill5, Skill6, Skill7, Skill8

PROJECTS
[Project Name]
- Action verb + what you built + technology used
- Action verb + result or impact achieved

EDUCATION
[Degree] — [University] ([Year])

STRICT RULES:
1. Every section header in CAPITAL LETTERS
2. Use bullet point • for every list item
3. Never write paragraphs in Skills or Projects
4. Every missing keyword must appear at least once
5. Use exact keywords — no synonyms
6. Action verbs: Built, Developed, Implemented,
   Designed, Automated, Integrated, Optimized
7. NO markdown — no ** no ## no __
8. Blank line between every section

Return ONLY the resume. No explanation."""

        completion = groq_rewrite_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=2500,
            messages=[
                {
                    "role":    "system",
                    "content": "You are an expert ATS resume writer. Return only the rewritten resume text."
                },
                {
                    "role":    "user",
                    "content": rewrite_prompt
                }
            ]
        )

        rewritten = completion.choices[0].message.content or ""
        return jsonify({
            "rewritten_resume":  rewritten,
            "keywords_injected": missing_keywords
        })

    except Exception as e:
        print(f"Rewrite error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================
# PORTFOLIO INTEGRATION — /candidate/ats/upload_portfolio
# ============================================================
@ats_bp.route('/candidate/ats/upload_portfolio', methods=['POST'])
def ats_upload_portfolio():
    try:
        user, _ = ensure_candidate_access()
        if not user: return jsonify({"error": "Unauthorized"}), 401
        
        resume_file = request.files.get('resume')
        ats_score = request.form.get('ats_score')
        
        if not resume_file:
            return jsonify({"error": "Resume file required"}), 400
            
        # 1. Clear existing resume if any (only 1 resume allowed)
        existing_resume = PortfolioItem.query.filter_by(
            candidate_user_id=user.id, 
            item_type='resume'
        ).first()
        
        # 2. Check total limit (5 items)
        if not existing_resume and len(user.portfolio_items) >= 5:
            return jsonify({"error": "Portfolio limit reached (5 seats). Delete an item first."}), 400

        if existing_resume:
            db.session.delete(existing_resume)
            db.session.flush()
            
        # 3. Save new resume
        new_item = PortfolioItem(
            candidate_user_id=user.id,
            label=f"Resume (Score: {ats_score}%)",
            item_type='resume',
            file_name=resume_file.filename,
            file_content=resume_file.read(),
            content_type=resume_file.content_type,
            ats_score=int(float(ats_score)) if ats_score else None
        )
        
        db.session.add(new_item)
        db.session.commit()
        
        return jsonify({"success": True, "message": "Resume uploaded to Portfolio Seat 1!"})

    except Exception as e:
        print(f"Portfolio upload error: {e}")
        return jsonify({"error": str(e)}), 500