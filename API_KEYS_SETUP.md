# API Keys Setup Guide

## 📍 Where to Put Your API Keys

All API keys go in the **`.env` file** in your project root directory:
```
c:\Users\lenovo\OneDrive\Desktop\the bird job\.env
```

---

## 🔑 API Keys to Configure

### 1. **Groq API** (Recommended)
```env
GROQ_API_KEY=your_groq_api_key_here
```
- **Get it from:** https://console.groq.com
- **Why Groq?** Fast, free tier available, no credit card needed initially
- **Status:** Preferred provider in the app

### 2. **Google Gemini API**
```env
GEMINI_API_KEY=your_gemini_api_key_here
```
- **Get it from:** https://aistudio.google.com/app/apikeys
- **Setup:** Enable Generative AI API in Google Cloud
- **Status:** Fallback provider if Groq fails

### 3. **Ollama (Local LLM - Optional)**
```env
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=llama2
```
- **Get it from:** https://ollama.ai
- **How to use:** 
  - Install Ollama
  - Run: `ollama serve`
  - Models available: llama2, mistral, neural-chat, etc.
- **Status:** Works offline, no API key needed

### 4. **ATS Service API**
```env
ATS_API_KEY=your_ats_api_key_here
ATS_API_URL=https://api.youratsservice.com/scan
```
- **Examples:** Workable, Lever, or custom ATS service
- **Status:** Falls back to local scoring if not configured

### 5. **Google OAuth** (Already existing)
```env
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
```

---

## 📋 Complete `.env` File Example

```env
DEBUG=True
SECRET_KEY=your-super-secret-key-here

# Database (for production)
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Google OAuth
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxx

# Groq API
GROQ_API_KEY=gsk_xxx

# Gemini API
GEMINI_API_KEY=AIzaSyD_xxx

# Ollama (Local LLM)
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# ATS Service
ATS_API_KEY=your_ats_key_here
ATS_API_URL=https://api.atsservice.com/scan

# Job APIs
JOBS_API_URL=https://remotive.com/api/remote-jobs
```

---

## 🚀 How the App Uses APIs

### Priority Order (Fallback Chain):
1. **Groq** → Fastest, cheapest
2. **Gemini** → Good quality, needs Google Cloud
3. **Ollama** → Local, offline, free
4. **ATS Service** → If you have external ATS
5. **Local Scoring** → Fallback if all else fail

### Smart Fallback Example:
```python
from ai_helper import analyze_resume_with_ai

score, feedback, provider_used = analyze_resume_with_ai(
    resume_text="...",
    job_description="...",
    preferred_provider='groq'  # Try Groq first
)
# If Groq fails → tries Gemini → tries Ollama → uses local
```

---

## 💻 For Development (Local)

**Minimum Setup:**
1. Add `GROQ_API_KEY` to `.env`
2. Get free key from https://console.groq.com
3. No other keys needed initially

**With Local LLM (Offline):**
1. Install Ollama: https://ollama.ai
2. Run: `ollama serve`
3. Set `OLLAMA_API_URL=http://localhost:11434`
4. No API key needed!

---

## ☁️ For Production (Render)

Go to **Render Dashboard** → **Your App** → **Environment Variables**

Add each line from your `.env` file:

| Key | Value |
|-----|-------|
| `GROQ_API_KEY` | `gsk_xxxxx` |
| `GEMINI_API_KEY` | `AIzaSyD_xxxxx` |
| `DATABASE_URL` | `postgresql://...` |
| etc. | ... |

---

## 🔄 Current Implementation

### ATS Scanner Flow:
```
User uploads resume
    ↓
Flask receives file
    ↓
analyze_resume_with_ai() called
    ↓
Tries Groq → Gemini → Ollama → Local
    ↓
Returns: (score, feedback, provider_used)
    ↓
Frontend displays results
```

---

## 📞 Getting API Keys (Quick Links)

| Service | Link | Free Tier | Time to Get |
|---------|------|-----------|------------|
| **Groq** | https://console.groq.com | ✅ Yes | 2 min |
| **Gemini** | https://aistudio.google.com | ✅ Yes | 5 min |
| **Ollama** | https://ollama.ai | ✅ Local | Download |

---

## ✅ Verify Setup

When you restart the app:
```bash
python app.py
```

Check logs to see which provider is being used. Example output:
```
✅ Groq configured
✅ Gemini configured
⚠️ Ollama not responding
⚠️ ATS API not configured
✅ Using Groq as primary provider
```

---

## 🔒 Security Tips

1. **Never commit `.env` to Git**
   - Already in `.gitignore` ✅

2. **Use environment variables for sensitive data**
   - `.env` for local development
   - Render Environment Variables for production

3. **Rotate keys regularly**
   - Change keys in `.env` or Render after deployment

4. **Don't share `.env` file**
   - Keep it local only

---

**Any issues?** The app will fall back to local scoring if no APIs are configured! 🚀
