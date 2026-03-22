"""
AI Helper Module
Handles AI ATS analysis and a local scoring fallback.
"""

import json
import re
from collections import Counter

from config.config import Config


STOPWORDS = {
    'a', 'about', 'across', 'after', 'all', 'also', 'an', 'and', 'any', 'applicant',
    'are', 'as', 'at', 'be', 'because', 'but', 'by', 'candidate', 'candidates',
    'communication', 'company', 'cross', 'day', 'degree', 'develop', 'developer',
    'developers', 'do', 'each', 'for', 'from', 'good', 'have', 'help', 'high',
    'ideal', 'in', 'include', 'including', 'into', 'is', 'it', 'job', 'knowledge',
    'looking', 'maintain', 'management', 'must', 'needed', 'of', 'on', 'or', 'our',
    'preferred', 'requirements', 'required', 'responsibilities', 'role', 'should',
    'skills', 'solid', 'strong', 'team', 'the', 'their', 'this', 'to', 'tools',
    'using', 'we', 'well', 'will', 'with', 'work', 'working', 'year', 'years', 'you',
    'your',
}

ACTION_VERBS = {
    'achieved', 'built', 'created', 'delivered', 'designed', 'developed', 'drove',
    'improved', 'implemented', 'increased', 'launched', 'led', 'managed', 'optimized',
    'reduced', 'resolved', 'scaled', 'streamlined',
}

SECTION_PATTERNS = {
    'summary': ('summary', 'profile', 'objective', 'about'),
    'experience': ('experience', 'employment', 'work history', 'professional experience'),
    'skills': ('skills', 'technical skills', 'core competencies', 'tech stack'),
    'education': ('education', 'academic', 'qualification', 'certification'),
    'projects': ('projects', 'project experience', 'personal projects', 'case studies'),
}


def normalize_text(text):
    text = str(text or '').replace('\x00', ' ')
    text = re.sub(r'\r\n?', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_terms(text):
    pattern = r'[A-Za-z][A-Za-z0-9\+\#\./-]{1,}'
    return [match.group(0) for match in re.finditer(pattern, text or '')]


def extract_job_keywords(job_description, limit=14):
    counts = Counter()
    for term in extract_terms(job_description):
        cleaned = term.strip('.,:;()[]{}').lower()
        if len(cleaned) < 2 or cleaned in STOPWORDS or cleaned.isdigit():
            continue
        counts[cleaned] += 1

    keywords = []
    for keyword, _count in counts.most_common(limit * 3):
        if keyword not in keywords:
            keywords.append(keyword)
        if len(keywords) >= limit:
            break
    return keywords


class AIProvider:
    """Base class for AI providers."""

    @staticmethod
    def is_configured(api_key):
        return bool((api_key or '').strip())

    @staticmethod
    def extract_json(text):
        try:
            return json.loads((text or '').strip())
        except Exception:
            pass

        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text or '')
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except Exception:
                pass

        brace_match = re.search(r'\{[\s\S]*\}', text or '')
        if brace_match:
            try:
                return json.loads(brace_match.group().strip())
            except Exception:
                pass

        return None

    @staticmethod
    def _safe_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _listify(value):
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    @staticmethod
    def _build_breakdown(score, keyword_score=None):
        base = max(0, min(100, AIProvider._safe_int(score, 0)))
        keywords = max(0, min(100, AIProvider._safe_int(keyword_score, base)))
        formatting = max(0, min(100, int(base * 0.95 + 8)))
        impact = max(20, min(100, int(base * 0.78 + 6)))
        skills = max(0, min(100, int((keywords + base) / 2)))
        return {
            'Keywords': keywords,
            'Formatting': formatting,
            'Impact Metrics': impact,
            'Skills Match': skills,
        }

    @staticmethod
    def normalize_analysis_result(result, resume_text='', job_description=''):
        if not isinstance(result, dict) or 'score' not in result:
            return None

        score = max(0, min(100, AIProvider._safe_int(result.get('score'), 0)))
        missing_keywords = AIProvider._listify(result.get('missing_keywords'))
        strengths = AIProvider._listify(result.get('strengths'))
        issues = AIProvider._listify(result.get('issues'))
        feedback = AIProvider._listify(result.get('feedback'))

        present_keywords = []
        extracted_keywords = extract_job_keywords(job_description)
        if extracted_keywords:
            lower_resume = (resume_text or '').lower()
            for keyword in extracted_keywords:
                if keyword.lower() in lower_resume and keyword not in present_keywords:
                    present_keywords.append(keyword)

        if not feedback:
            feedback = [f"OK: {item}" for item in strengths] + [f"Improve: {item}" for item in issues]
        if not strengths:
            strengths = [item.replace('OK: ', '', 1) for item in feedback if item.lower().startswith('ok:')][:4]
        if not issues:
            issues = [item.replace('Improve: ', '', 1) for item in feedback if item.lower().startswith('improve:')][:4]

        keyword_denominator = len(present_keywords) + len(missing_keywords)
        keyword_score = None
        if keyword_denominator:
            keyword_score = int((len(present_keywords) / keyword_denominator) * 100)

        breakdown = result.get('breakdown')
        if not isinstance(breakdown, dict) or not breakdown:
            breakdown = AIProvider._build_breakdown(score, keyword_score)

        return {
            'score': score,
            'feedback': feedback,
            'strengths': strengths,
            'issues': issues,
            'missing_keywords': missing_keywords,
            'present_keywords': present_keywords,
            'breakdown': breakdown,
        }


class LocalATSScorer:
    """Rule-based ATS scorer used when external AI providers fail."""

    @staticmethod
    def _clamp(value, minimum=0, maximum=100):
        return max(minimum, min(maximum, int(value)))

    @staticmethod
    def _section_score(resume_text):
        lower_text = (resume_text or '').lower()
        found = []
        for section, patterns in SECTION_PATTERNS.items():
            if any(pattern in lower_text for pattern in patterns):
                found.append(section)
        score = int((len(found) / len(SECTION_PATTERNS)) * 100)
        return score, found

    @staticmethod
    def _formatting_score(resume_text, section_score):
        lines = [line.strip() for line in (resume_text or '').splitlines() if line.strip()]
        bullet_lines = sum(1 for line in lines if line.startswith(('-', '*', '•')))
        bullet_bonus = min(18, bullet_lines * 3)
        email_bonus = 8 if re.search(r'[\w\.-]+@[\w\.-]+\.\w+', resume_text or '') else 0
        phone_bonus = 8 if re.search(r'(\+\d{1,3}\s*)?[\(\[]?\d{3,4}[\)\]]?[-\s]?\d{3}[-\s]?\d{3,4}', resume_text or '') else 0
        linkedin_bonus = 6 if 'linkedin.com' in (resume_text or '').lower() else 0
        word_count = len((resume_text or '').split())
        length_bonus = 10 if 180 <= word_count <= 900 else 0
        formatting = 28 + int(section_score * 0.45) + bullet_bonus + email_bonus + phone_bonus + linkedin_bonus + length_bonus
        return LocalATSScorer._clamp(formatting)

    @staticmethod
    def _impact_score(resume_text):
        text = resume_text or ''
        metric_hits = len(re.findall(r'(\d+%|\$\d+|\d+\+|\d+\s*(?:years?|months?)|\d{2,})', text, flags=re.IGNORECASE))
        action_hits = sum(1 for term in extract_terms(text) if term.lower() in ACTION_VERBS)
        score = 18 + min(52, metric_hits * 12) + min(24, action_hits * 4)
        return LocalATSScorer._clamp(score)

    @staticmethod
    def _skills_score(resume_text, keyword_score):
        text = (resume_text or '').lower()
        tech_hits = 0
        for term in ('python', 'java', 'javascript', 'sql', 'react', 'node', 'aws', 'excel', 'django', 'flask', 'api'):
            if term in text:
                tech_hits += 1
        score = int((keyword_score * 0.65) + min(35, tech_hits * 5))
        return LocalATSScorer._clamp(score)

    @staticmethod
    def analyze_resume(resume_text, job_description=''):
        resume_text = normalize_text(resume_text)
        job_description = normalize_text(job_description)

        keywords = extract_job_keywords(job_description)
        lower_resume = resume_text.lower()
        present_keywords = [keyword for keyword in keywords if keyword in lower_resume]
        missing_keywords = [keyword for keyword in keywords if keyword not in lower_resume]

        keyword_score = int((len(present_keywords) / len(keywords)) * 100) if keywords else 60
        section_score, found_sections = LocalATSScorer._section_score(resume_text)
        formatting_score = LocalATSScorer._formatting_score(resume_text, section_score)
        impact_score = LocalATSScorer._impact_score(resume_text)
        skills_score = LocalATSScorer._skills_score(resume_text, keyword_score)

        if job_description:
            score = round(
                (keyword_score * 0.42) +
                (formatting_score * 0.23) +
                (impact_score * 0.18) +
                (skills_score * 0.17)
            )
        else:
            score = round(
                (formatting_score * 0.35) +
                (impact_score * 0.25) +
                (skills_score * 0.25) +
                (section_score * 0.15)
            )

        score = LocalATSScorer._clamp(score)

        strengths = []
        issues = []

        if keyword_score >= 70:
            strengths.append('Your resume already matches many of the important job keywords.')
        elif present_keywords:
            issues.append(f"Add more role-specific keywords, especially: {', '.join(missing_keywords[:5])}.")
        else:
            issues.append('The resume is missing most of the role-specific keywords from the job description.')

        if formatting_score >= 70:
            strengths.append('The resume layout looks ATS-friendly with clear structure and contact details.')
        else:
            issues.append('Use clear ATS sections like Summary, Experience, Skills, and Education.')

        if impact_score >= 65:
            strengths.append('You included measurable impact, which helps recruiters trust your experience.')
        else:
            issues.append('Add more numbers, percentages, timelines, or business impact in your bullet points.')

        if 'skills' in found_sections or skills_score >= 65:
            strengths.append('Your skills appear visible enough for an ATS scan.')
        else:
            issues.append('Create a dedicated skills section so ATS systems can parse your tools and technologies faster.')

        word_count = len(resume_text.split())
        if word_count < 180:
            issues.append('The resume feels short. Add more relevant experience, projects, or achievements.')
        elif word_count > 900:
            issues.append('The resume is quite long. Trim less relevant content to improve ATS readability.')

        if not strengths:
            strengths.append('You have a usable base resume to improve from, even though it needs more tailoring.')
        if not issues:
            issues.append('Tailor the resume for each application and keep the most relevant keywords near the top.')

        feedback = [f"OK: {item}" for item in strengths] + [f"Improve: {item}" for item in issues]

        return {
            'score': score,
            'feedback': feedback,
            'strengths': strengths[:4],
            'issues': issues[:5],
            'missing_keywords': missing_keywords[:10],
            'present_keywords': present_keywords[:10],
            'breakdown': {
                'Keywords': LocalATSScorer._clamp(keyword_score),
                'Formatting': formatting_score,
                'Impact Metrics': impact_score,
                'Skills Match': skills_score,
            },
        }


class GeminiProvider(AIProvider):
    """Google Gemini API provider."""

    @staticmethod
    def analyze_resume(resume_text, job_description=''):
        if not GeminiProvider.is_configured(Config.GEMINI_API_KEY):
            return None, 'Gemini API key not configured'

        try:
            import google.generativeai as genai

            genai.configure(api_key=Config.GEMINI_API_KEY)

            prompt = f"""You are an expert ATS (Applicant Tracking System) analyzer.
Analyze the resume against the job description carefully.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description if job_description else "No job description provided. Do general ATS analysis."}

IMPORTANT: Return ONLY a valid JSON object. No markdown, no backticks, no extra text.
Exactly this format:
{{
    "score": <integer between 0 and 100>,
    "missing_keywords": ["keyword1", "keyword2", "keyword3"],
    "issues": ["issue1", "issue2", "issue3"],
    "strengths": ["strength1", "strength2", "strength3"],
    "feedback": ["feedback point 1", "feedback point 2", "feedback point 3"]
}}"""

            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)

            result = AIProvider.extract_json(getattr(response, 'text', ''))
            normalized = AIProvider.normalize_analysis_result(result, resume_text, job_description)
            if normalized:
                return normalized, None

            print(f"[Gemini] JSON parse failed. Raw response: {getattr(response, 'text', '')[:300]}")
            return None, 'Response parse failed'
        except Exception as exc:
            return None, f'Gemini API error: {str(exc)}'


class GroqProvider(AIProvider):
    """Groq API provider."""

    @staticmethod
    def analyze_resume(resume_text, job_description=''):
        if not GroqProvider.is_configured(Config.GROQ_API_KEY):
            return None, 'Groq API key not configured'

        try:
            from groq import Groq

            client = Groq(api_key=Config.GROQ_API_KEY)

            prompt = f"""You are an expert ATS (Applicant Tracking System) analyzer.
Analyze the resume against the job description carefully.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description if job_description else "No job description provided. Do general ATS analysis."}

IMPORTANT: Return ONLY a valid JSON object. No markdown, no backticks, no extra text.
Exactly this format:
{{
    "score": <integer between 0 and 100>,
    "missing_keywords": ["keyword1", "keyword2", "keyword3"],
    "issues": ["issue1", "issue2", "issue3"],
    "strengths": ["strength1", "strength2", "strength3"],
    "feedback": ["feedback point 1", "feedback point 2", "feedback point 3"]
}}"""

            message = client.chat.completions.create(
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are an ATS resume analyzer. Always respond with valid JSON only. No markdown, no extra text, no backticks.',
                    },
                    {
                        'role': 'user',
                        'content': prompt,
                    },
                ],
                model=Config.GROQ_MODEL,
                temperature=0.1,
                max_tokens=1000,
            )

            response_text = message.choices[0].message.content
            result = AIProvider.extract_json(response_text)
            normalized = AIProvider.normalize_analysis_result(result, resume_text, job_description)
            if normalized:
                return normalized, None

            print(f"[Groq] JSON parse failed. Raw response: {response_text[:300]}")
            return None, 'Response parse failed'
        except Exception as exc:
            return None, f'Groq API error: {str(exc)}'


def run_ai_resume_analysis(resume_text, job_description='', preferred_provider='groq'):
    """Run AI analysis only and return a structured payload if any provider succeeds."""

    providers = {
        'groq': GroqProvider,
        'gemini': GeminiProvider,
    }
    last_error = 'All AI providers failed.'

    if preferred_provider in providers:
        analysis, error = providers[preferred_provider].analyze_resume(resume_text, job_description)
        if analysis is not None:
            return analysis, preferred_provider, None
        last_error = error

    for provider_name in ('groq', 'gemini'):
        if provider_name == preferred_provider:
            continue
        analysis, error = providers[provider_name].analyze_resume(resume_text, job_description)
        if analysis is not None:
            return analysis, provider_name, None
        last_error = error

    return None, 'failed', last_error


def analyze_resume_with_ai(resume_text, job_description='', preferred_provider='groq'):
    """
    Preserve the old interface for callers that only need score + feedback.
    """

    analysis, provider_used, error = run_ai_resume_analysis(
        resume_text,
        job_description,
        preferred_provider=preferred_provider,
    )
    if analysis is not None:
        return analysis['score'], analysis.get('feedback', []), provider_used

    return None, error or 'All AI providers failed. Please check API keys.', 'failed'


def analyze_resume_with_backup(resume_text, job_description='', preferred_provider='groq'):
    """
    Analyze a resume with AI when available, then fall back to local ATS scoring.

    Returns:
        (analysis_dict, provider_used, used_fallback)
    """

    analysis, provider_used, error = run_ai_resume_analysis(
        resume_text,
        job_description,
        preferred_provider=preferred_provider,
    )
    if analysis is not None:
        analysis['fallback_reason'] = None
        return analysis, provider_used, False

    fallback_analysis = LocalATSScorer.analyze_resume(resume_text, job_description)
    fallback_analysis['fallback_reason'] = error
    return fallback_analysis, 'local_fallback', True
