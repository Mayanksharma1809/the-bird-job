/* ATS scoring logic for client-side rule-based calculation. */
(function atsScannerModule(globalScope) {
    'use strict';

    const STOP_WORDS = new Set([
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'but', 'by', 'for', 'from', 'has',
        'have', 'in', 'is', 'it', 'its', 'of', 'on', 'or', 'that', 'the', 'their',
        'this', 'to', 'we', 'with', 'you', 'your', 'our', 'will', 'can', 'should'
    ]);

    const SKILL_TERMS = [
        'python', 'java', 'javascript', 'typescript', 'node', 'node.js', 'react', 'angular', 'vue',
        'django', 'flask', 'spring', 'dotnet', '.net', 'c', 'c++', 'c#', 'go', 'rust',
        'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'rest', 'rest api', 'graphql',
        'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform', 'linux', 'git',
        'html', 'css', 'bootstrap', 'tailwind', 'figma', 'jira', 'agile', 'scrum',
        'pandas', 'numpy', 'machine learning', 'deep learning', 'nlp', 'data analysis',
        'excel', 'power bi', 'tableau', 'selenium', 'pytest', 'jest', 'ci/cd'
    ];

    const DEGREE_RULES = [
        { level: 1, aliases: ['high school', 'secondary school'] },
        { level: 2, aliases: ['associate', 'diploma'] },
        { level: 3, aliases: ['bachelor', 'b.tech', 'btech', 'b.e', 'be', 'b.sc', 'bs', 'ba'] },
        { level: 4, aliases: ['master', 'm.tech', 'mtech', 'm.e', 'm.sc', 'ms', 'mba', 'ma'] },
        { level: 5, aliases: ['phd', 'doctorate', 'd.phil'] }
    ];

    const MONTH_INDEX = {
        jan: 0, january: 0,
        feb: 1, february: 1,
        mar: 2, march: 2,
        apr: 3, april: 3,
        may: 4,
        jun: 5, june: 5,
        jul: 6, july: 6,
        aug: 7, august: 7,
        sep: 8, sept: 8, september: 8,
        oct: 9, october: 9,
        nov: 10, november: 10,
        dec: 11, december: 11
    };

    function clamp(value, min, max) {
        return Math.min(max, Math.max(min, value));
    }

    function roundScore(value) {
        return Number(clamp(value || 0, 0, 100).toFixed(2));
    }

    function normalizeSpaces(text) {
        return String(text || '').replace(/\s+/g, ' ').trim();
    }

    function normalizeAlphaNumeric(text) {
        return normalizeSpaces(String(text || '').toLowerCase().replace(/[^a-z0-9+#.\s]/g, ' '));
    }

    function escapeRegExp(text) {
        return String(text || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function tokenizeKeywords(text) {
        return normalizeAlphaNumeric(text)
            .split(' ')
            .map(token => token.trim())
            .filter(token => token.length > 2 && !STOP_WORDS.has(token));
    }

    function extractKeywordsFromJobDescription(jobDescriptionText) {
        return Array.from(new Set(tokenizeKeywords(jobDescriptionText)));
    }

    function calculateKeywordMatchScore(resumeText, jobDescriptionText) {
        const jdKeywords = extractKeywordsFromJobDescription(jobDescriptionText);
        if (!jdKeywords.length) {
            return 0;
        }
        const resumeTokens = new Set(tokenizeKeywords(resumeText));
        const foundCount = jdKeywords.filter(keyword => resumeTokens.has(keyword)).length;
        return roundScore((foundCount / jdKeywords.length) * 100);
    }

    function extractRequiredSkills(jobDescriptionText) {
        const jdLower = normalizeAlphaNumeric(jobDescriptionText);
        const matchedSkills = new Set();

        SKILL_TERMS.forEach((skill) => {
            const skillPattern = new RegExp(`\\b${escapeRegExp(skill.toLowerCase())}\\b`, 'i');
            if (skillPattern.test(jdLower)) {
                matchedSkills.add(skill.toLowerCase());
            }
        });

        const explicitSkillsMatch = String(jobDescriptionText || '').match(/skills?\s*[:\-]\s*([^\n]+)/i);
        if (explicitSkillsMatch && explicitSkillsMatch[1]) {
            explicitSkillsMatch[1]
                .split(/[,/|]/)
                .map(item => normalizeAlphaNumeric(item))
                .filter(Boolean)
                .forEach(item => matchedSkills.add(item));
        }

        return Array.from(matchedSkills);
    }

    function calculateSkillsMatchScore(resumeText, jobDescriptionText) {
        const requiredSkills = extractRequiredSkills(jobDescriptionText);
        if (!requiredSkills.length) {
            return 0;
        }
        const resumeLower = normalizeAlphaNumeric(resumeText);
        const matchedCount = requiredSkills.filter((skill) => {
            const pattern = new RegExp(`\\b${escapeRegExp(skill)}\\b`, 'i');
            return pattern.test(resumeLower);
        }).length;
        return roundScore((matchedCount / requiredSkills.length) * 100);
    }

    function extractRequiredYears(jobDescriptionText) {
        const jd = String(jobDescriptionText || '').toLowerCase();
        const plusYearsMatch = jd.match(/(\d+)\s*\+?\s*years?/i);
        if (plusYearsMatch) {
            return Number(plusYearsMatch[1]);
        }
        const rangeMatch = jd.match(/(\d+)\s*[-to]+\s*(\d+)\s*years?/i);
        if (rangeMatch) {
            return Number(rangeMatch[1]);
        }
        return null;
    }

    function parseDateToken(token) {
        const value = String(token || '').trim().toLowerCase();
        if (!value) {
            return null;
        }

        if (/present|current|now|today/.test(value)) {
            return new Date();
        }

        const monthYearMatch = value.match(/([a-z]{3,9})\s+(\d{4})/);
        if (monthYearMatch) {
            const month = MONTH_INDEX[monthYearMatch[1]];
            const year = Number(monthYearMatch[2]);
            if (Number.isFinite(month) && Number.isFinite(year)) {
                return new Date(year, month, 1);
            }
        }

        const yearMatch = value.match(/\b(19|20)\d{2}\b/);
        if (yearMatch) {
            return new Date(Number(yearMatch[0]), 0, 1);
        }
        return null;
    }

    function monthDiff(startDate, endDate) {
        if (!startDate || !endDate) {
            return 0;
        }
        const months = (endDate.getFullYear() - startDate.getFullYear()) * 12 + (endDate.getMonth() - startDate.getMonth());
        return Math.max(0, months);
    }

    function extractTotalExperienceYears(resumeText) {
        const resumeRaw = String(resumeText || '');
        const dateRangeRegex = /((?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}|\b\d{4}\b)\s*(?:-|to|through)\s*((?:present|current|now)|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}|\b\d{4}\b)/gi;

        let totalMonths = 0;
        let match = dateRangeRegex.exec(resumeRaw);
        while (match) {
            const start = parseDateToken(match[1]);
            const end = parseDateToken(match[2]);
            totalMonths += monthDiff(start, end);
            match = dateRangeRegex.exec(resumeRaw);
        }

        if (!totalMonths) {
            const yearsMentionMatch = resumeRaw.match(/(\d+(?:\.\d+)?)\s*\+?\s*years?/i);
            if (yearsMentionMatch) {
                return Number(yearsMentionMatch[1]);
            }
            return null;
        }

        return Number((totalMonths / 12).toFixed(2));
    }

    function calculateExperienceMatchScore(resumeText, jobDescriptionText) {
        const requiredYears = extractRequiredYears(jobDescriptionText);
        const resumeYears = extractTotalExperienceYears(resumeText);
        if (requiredYears === null || resumeYears === null) {
            return 20;
        }

        if (Math.round(resumeYears) === requiredYears) {
            return 90;
        }
        if (resumeYears > requiredYears) {
            return 80;
        }
        return 50;
    }

    function findDegreeInText(text) {
        const lowerText = String(text || '').toLowerCase();
        for (const rule of DEGREE_RULES) {
            for (const alias of rule.aliases) {
                const aliasPattern = new RegExp(`\\b${escapeRegExp(alias)}\\b`, 'i');
                if (aliasPattern.test(lowerText)) {
                    return { level: rule.level, alias };
                }
            }
        }
        return null;
    }

    function extractDegreeField(text) {
        const fieldMatch = String(text || '').toLowerCase().match(/\b(?:in|of)\s+([a-z][a-z\s&/-]{2,60})/i);
        if (!fieldMatch || !fieldMatch[1]) {
            return '';
        }
        return fieldMatch[1].replace(/\s+/g, ' ').trim();
    }

    function extractRequiredDegree(jobDescriptionText) {
        const degree = findDegreeInText(jobDescriptionText);
        if (!degree) {
            return null;
        }
        return {
            level: degree.level,
            field: extractDegreeField(jobDescriptionText)
        };
    }

    function extractResumeDegrees(resumeText) {
        const lines = String(resumeText || '').split(/\r?\n/);
        const matches = [];

        lines.forEach((line) => {
            const degree = findDegreeInText(line);
            if (degree) {
                matches.push({
                    level: degree.level,
                    field: extractDegreeField(line)
                });
            }
        });

        if (!matches.length) {
            const resumeDegree = findDegreeInText(resumeText);
            if (resumeDegree) {
                matches.push({
                    level: resumeDegree.level,
                    field: extractDegreeField(resumeText)
                });
            }
        }

        return matches;
    }

    function fieldsMatch(requiredField, resumeField) {
        if (!requiredField) {
            return true;
        }
        if (!resumeField) {
            return false;
        }
        const required = normalizeAlphaNumeric(requiredField);
        const resume = normalizeAlphaNumeric(resumeField);
        return required && resume && (resume.includes(required) || required.includes(resume));
    }

    function calculateEducationMatchScore(resumeText, jobDescriptionText) {
        const requiredDegree = extractRequiredDegree(jobDescriptionText);
        if (!requiredDegree) {
            return 30;
        }

        const resumeDegrees = extractResumeDegrees(resumeText);
        if (!resumeDegrees.length) {
            return 30;
        }

        const exactMatch = resumeDegrees.some((degree) => degree.level === requiredDegree.level && fieldsMatch(requiredDegree.field, degree.field));
        if (exactMatch) {
            return 95;
        }

        const hasHigher = resumeDegrees.some((degree) => degree.level > requiredDegree.level);
        if (hasHigher) {
            return 85;
        }

        const hasDifferentField = resumeDegrees.some((degree) => degree.level === requiredDegree.level && !fieldsMatch(requiredDegree.field, degree.field));
        if (hasDifferentField) {
            return 65;
        }

        return 30;
    }

    function calculateFormattingScore(resumeText) {
        const resumeRaw = String(resumeText || '');
        const resumeLower = resumeRaw.toLowerCase();

        const sectionChecks = [
            /\bexperience\b/i.test(resumeLower),
            /\bskills?\b/i.test(resumeLower),
            /\beducation\b/i.test(resumeLower)
        ];
        const sectionScore = (sectionChecks.filter(Boolean).length / 3) * 34;

        const hasTableOrImage = /<table|<\/table>|<img|\.png\b|\.jpg\b|\.jpeg\b|\.gif\b|\|\s*[^|]+\s*\|/i.test(resumeRaw);
        const tableImageScore = hasTableOrImage ? 0 : 33;

        const hasEmail = /[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/i.test(resumeRaw);
        const hasPhone = /(?:\+?\d[\d\s\-()]{7,}\d)/.test(resumeRaw);
        const hasLinkedIn = /linkedin\.com\/in\//i.test(resumeRaw);
        const contactScore = (hasEmail || hasPhone || hasLinkedIn) ? 33 : 0;

        return roundScore(sectionScore + tableImageScore + contactScore);
    }

    function calculateAtsScores(resumeText, jobDescriptionText) {
        const keywordMatch = calculateKeywordMatchScore(resumeText, jobDescriptionText);
        const skillsMatch = calculateSkillsMatchScore(resumeText, jobDescriptionText);
        const experienceMatch = calculateExperienceMatchScore(resumeText, jobDescriptionText);
        const educationMatch = calculateEducationMatchScore(resumeText, jobDescriptionText);
        const formatting = calculateFormattingScore(resumeText);

        const overallScore = roundScore(
            (keywordMatch * 0.35) +
            (skillsMatch * 0.25) +
            (experienceMatch * 0.20) +
            (educationMatch * 0.10) +
            (formatting * 0.10)
        );

        return {
            keyword_match: keywordMatch,
            skills_match: skillsMatch,
            experience_match: experienceMatch,
            education_match: educationMatch,
            formatting: formatting,
            overall_score: overallScore
        };
    }

    async function parseApiResponse(response) {
        const rawText = await response.text();
        let parsed = null;
        if (rawText) {
            try {
                parsed = JSON.parse(rawText);
            } catch (err) {
                parsed = null;
            }
        }
        return { parsed, rawText };
    }

    async function callAtsScoringApi(payload, endpoint) {
        const response = await fetch(endpoint || '/candidate/ats/score', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload || {})
        });

        const { parsed, rawText } = await parseApiResponse(response);
        const data = parsed || {};
        if (!response.ok) {
            const msg = data.error || rawText || `ATS scoring API request failed (${response.status})`;
            throw new Error(msg);
        }
        return data;
    }

    async function scoreResumeWithScanApi(options) {
        const payload = options || {};
        const formData = new FormData();
        formData.append('resume', payload.resumeFile);
        formData.append('job_description', payload.jobDescription || '');
        if (payload.jobDescriptionFile) {
            formData.append('job_description_file', payload.jobDescriptionFile);
        }

        const response = await fetch(payload.endpoint || '/candidate/ats/scan', {
            method: 'POST',
            body: formData
        });
        const { parsed, rawText } = await parseApiResponse(response);
        const data = parsed || {};

        const explicitFailure = data && data.success === false;
        if (!response.ok || explicitFailure) {
            const msg = data.error || rawText || `ATS scan failed (${response.status})`;
            throw new Error(msg);
        }

        const resumeText = data.resume_text || '';
        const jdText = data.job_description_text || payload.jobDescription || '';
        const ruleScores = calculateAtsScores(resumeText, jdText);

        return {
            ...data,
            rule_scores: ruleScores
        };
    }

    globalScope.calculateAtsScores = calculateAtsScores;
    globalScope.callAtsScoringApi = callAtsScoringApi;
    globalScope.scoreResumeWithScanApi = scoreResumeWithScanApi;
}(window));


