"""
AI Helper Module
Handles API calls to Gemini, Groq, Ollama, and ATS services.
"""

import os
import json
import requests
from config.config import Config


class AIProvider:
    """Base class for AI providers."""
    
    @staticmethod
    def is_configured(api_key):
        """Check if API key is configured."""
        return bool((api_key or '').strip())


class GeminiProvider(AIProvider):
    """Google Gemini API provider."""
    
    @staticmethod
    def analyze_resume(resume_text, job_description=''):
        """
        Analyze resume using Gemini API.
        Returns: (score, feedback_list)
        """
        if not GeminiProvider.is_configured(Config.GEMINI_API_KEY):
            return None, "Gemini API key not configured"
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=Config.GEMINI_API_KEY)
            
            prompt = f"""Analyze this resume for ATS compatibility and job match.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}

Provide:
1. ATS score (0-100)
2. List of missing keywords
3. 3 main issues to fix
4. 3 strengths of the resume

Format as JSON."""
            
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            
            # Parse JSON response
            try:
                result = json.loads(response.text)
                return result.get('score', 65), result.get('feedback', [])
            except:
                return 65, [response.text[:200]]
                
        except Exception as e:
            return None, f"Gemini API error: {str(e)}"


class GroqProvider(AIProvider):
    """Groq API provider."""
    
    @staticmethod
    def analyze_resume(resume_text, job_description=''):
        """
        Analyze resume using Groq API.
        Returns: (score, feedback_list)
        """
        if not GroqProvider.is_configured(Config.GROQ_API_KEY):
            return None, "Groq API key not configured"
        
        try:
            from groq import Groq
            
            client = Groq(api_key=Config.GROQ_API_KEY)
            
            prompt = f"""Analyze this resume for ATS compatibility and job match.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}

Provide:
1. ATS score (0-100)
2. List of missing keywords
3. 3 main issues to fix
4. 3 strengths of the resume

Format as JSON."""
            
            message = client.chat.completions.create(
                messages=[
                    {"role": "user", "content": prompt}
                ],
                model=Config.GROQ_MODEL,
            )
            
            response_text = message.choices[0].message.content
            
            try:
                result = json.loads(response_text)
                return result.get('score', 65), result.get('feedback', [])
            except:
                return 65, [response_text[:200]]
                
        except Exception as e:
            return None, f"Groq API error: {str(e)}"


class OllamaProvider(AIProvider):
    """Ollama local LLM provider."""
    
    @staticmethod
    def analyze_resume(resume_text, job_description=''):
        """
        Analyze resume using Ollama (local LLM).
        Returns: (score, feedback_list)
        """
        try:
            prompt = f"""Analyze this resume for ATS compatibility and job match.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}

Provide:
1. ATS score (0-100)
2. List of missing keywords
3. 3 main issues to fix
4. 3 strengths of the resume

Format as JSON."""
            
            response = requests.post(
                f'{Config.OLLAMA_API_URL}/api/generate',
                json={
                    'model': Config.OLLAMA_MODEL,
                    'prompt': prompt,
                    'stream': False,
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')
                
                try:
                    data = json.loads(response_text)
                    return data.get('score', 65), data.get('feedback', [])
                except:
                    return 65, [response_text[:200]]
            else:
                return None, "Ollama service not responding"
                
        except requests.exceptions.ConnectionError:
            return None, "Ollama not running. Start with: ollama serve"
        except Exception as e:
            return None, f"Ollama error: {str(e)}"


class ATSProvider(AIProvider):
    """ATS Resume Scanning Service provider."""
    
    @staticmethod
    def scan_resume(resume_text, job_description=''):
        """
        Scan resume using external ATS service.
        Returns: (score, feedback_list)
        """
        if not ATSProvider.is_configured(Config.ATS_API_KEY):
            return None, "ATS API key not configured"
        
        if not Config.ATS_API_URL:
            return None, "ATS API URL not configured"
        
        try:
            response = requests.post(
                Config.ATS_API_URL,
                headers={
                    'Authorization': f'Bearer {Config.ATS_API_KEY}',
                    'Content-Type': 'application/json',
                },
                json={
                    'resume': resume_text,
                    'job_description': job_description,
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('score', 0), data.get('feedback', [])
            else:
                return None, f"ATS service error: {response.status_code}"
                
        except Exception as e:
            return None, f"ATS API error: {str(e)}"


def analyze_resume_with_ai(resume_text, job_description='', preferred_provider='groq'):
    """
    Analyze resume using the specified AI provider.
    Falls back to other providers if the preferred one fails.
    
    Args:
        resume_text: Resume content
        job_description: Job description to match against
        preferred_provider: 'groq', 'gemini', 'ollama', 'ats', or 'auto'
    
    Returns:
        (score, feedback_list, provider_used)
    """
    
    providers = {
        'groq': GroqProvider,
        'gemini': GeminiProvider,
        'ollama': OllamaProvider,
        'ats': ATSProvider,
    }
    
    # Try preferred provider first
    if preferred_provider in providers:
        score, feedback = providers[preferred_provider].analyze_resume(
            resume_text, job_description
        )
        if score is not None:
            return score, feedback, preferred_provider
    
    # Fallback chain: Groq → Gemini → Ollama → ATS → Basic
    fallback_order = ['groq', 'gemini', 'ollama', 'ats']
    
    for provider_name in fallback_order:
        if provider_name == preferred_provider:
            continue  # Already tried
        
        score, feedback = providers[provider_name].analyze_resume(
            resume_text, job_description
        )
        if score is not None:
            return score, feedback, provider_name
    
    # If all AI providers fail, use basic scoring
    from candidate_dashboard_routes import calculate_ats_score
    score, feedback = calculate_ats_score(resume_text, job_description)
    return score, feedback, 'local'
