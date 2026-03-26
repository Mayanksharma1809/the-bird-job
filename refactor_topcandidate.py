import re

def refactor_template():
    filepath = 'C:/Users/lenovo/OneDrive/Desktop/THEbirdJOB/templates/topcandidate.html'
    with open(filepath, 'r', encoding='utf-8') as f:
        t: str = f.read()

    # Fix the parts splitting quotes
    t = t.replace("'Unknown'", '\"Unknown\"')
    t = t.replace("'?')", '\"?\")')
    t = t.replace("else ''))", 'else \"\"))')

    # Fix podium card viewing
    for cx in ['c1', 'c2', 'c3']:
        t = re.sub(
            fr'onclick="showToast\(\'Viewing \{\{ {cx}\.candidate_name[^\}]+\}\}\\\'s full profile\.\.\.\'\)"',
            f'data-candidate-name="{{{{ {cx}.candidate_name }}}}" onclick="showCandidateProfile(this, \'Viewing\')"',
            t
        )
        # Also clean up the random </div> the user added
        t = t.replace(f'onclick="showCandidateProfile(this, \'Viewing\')"></div>',
                      f'onclick="showCandidateProfile(this, \'Viewing\')">')

    # Fix leaderboard viewing
    t = t.replace(
        "onclick=\"showToast('Profile view coming soon')\"",
        "data-candidate-name=\"{{ c.candidate_name }}\" onclick=\"showCandidateProfile(this, 'Profile view coming soon')\""
    )

    # Fix width bars
    t = re.sub(
        r'style="width:\{\{\s*([^\}]+)\s*\}\}%;([^"]+)"',
        r'class="p-bar-fill js-width" data-width="{{ \1 }}%" style="\2"',
        t
    )

    # Fix msg buttons
    t = re.sub(
        r'onclick="event\.stopPropagation\(\);\s*window\.location\.href=\'\{\{ url_for\(\'employer_messages_page\'\) \}\}\'"',
        r'data-url="{{ url_for(\'employer_messages_page\') }}" onclick="handleMsg(this, event)"',
        t
    )

    # Fix lb-score inline logic
    # <div class="lb-score" style="{% if loop.index > 3 %}color:var(--text);font-size:0.9rem{% endif %}">{{
    t = re.sub(
        r'<div class="lb-score" style="\{% if loop\.index > 3 %\}color:var\(--text\);font-size:0\.9rem\{% endif %\}">',
        r'<div class="lb-score score-rank-{{ loop.index }}">',
        t
    )

    # Fix lb-avatar inline logic
    # style="background:{% if loop.index == 1 %}var(--orange-dim){% elif loop.index == 2 %}rgba(148,163,184,0.1){% elif loop.index == 3 %}rgba(205,124,46,0.1){% else %}rgba(168,85,247,0.1){% endif %};color:{% if loop.index == 1 %}var(--orange){% elif loop.index == 2 %}#94a3b8{% elif loop.index == 3 %}#cd7c2e{% else %}#a855f7{% endif %}"
    t = re.sub(
        r'<div class="lb-avatar"\s*style="background:\{%.*?\{% endif %\}">',
        r'<div class="lb-avatar bg-rank-{{ loop.index }}">',
        t, flags=re.DOTALL
    )

    # Add missing CSS
    css_to_add = '''
    .bg-rank-1 { background: var(--orange-dim) !important; color: var(--orange) !important; }
    .bg-rank-2 { background: rgba(148,163,184,0.1) !important; color: #94a3b8 !important; }
    .bg-rank-3 { background: rgba(205,124,46,0.1) !important; color: #cd7c2e !important; }
    .lb-avatar { background: rgba(168,85,247,0.1); color: #a855f7; }
    .score-rank-1, .score-rank-2, .score-rank-3 { color: var(--orange); }
    .score-rank-2 { color: #94a3b8; }
    .score-rank-3 { color: #cd7c2e; }
    .lb-score { color: var(--text); font-size: 0.9rem; }
    '''
    if '.bg-rank-1' not in t:
        t = t.replace('</style>', css_to_add + '\n  </style>')

    # Add missing JS
    js_to_add = '''
    function showCandidateProfile(el, action) {
      const name = el.getAttribute('data-candidate-name');
      showToast(`${action == 'Viewing' ? 'Viewing' : action} ${name ? name + '\\'s full profile...' : ''}`);
    }

    function handleMsg(el, e) {
      e.stopPropagation();
      window.location.href = el.getAttribute('data-url');
    }

    document.querySelectorAll('.js-width').forEach(el => {
      el.style.width = el.getAttribute('data-width');
    });
    '''
    if 'function handleMsg' not in t:
        t = t.replace('</script>', js_to_add + '\n  </script>')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(t)

if __name__ == '__main__':
    refactor_template()
    print("SUCCESS")
