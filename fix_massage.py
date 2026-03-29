import re

with open('templates/candidate_massage.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace basic strings
html = html.replace('Candidate Messages |', 'Employer Messages |')
html = html.replace('candidate_dashboard', 'employer_dashboard')
html = html.replace('candidate_messages_page', 'employer_messages_page')
html = html.replace('data-employer-id', 'data-candidate-id')
html = html.replace('currentEmployerId', 'currentCandidateId')
html = html.replace('employer_id', 'candidate_id')
html = html.replace('empId', 'candId')
html = html.replace('employerId', 'candidateId')
html = html.replace('/api/candidate/', '/api/employer/')
html = html.replace('Search employers...', 'Search candidates...')
html = html.replace('Employer Name', 'Candidate Name')
html = html.replace('Apply for jobs to start chatting with employers.', 'Go to Applications to start chatting with candidates.')

# Replace Nav Links explicitly
nav_links_target = """    <div class="nav-links">
        <a href="{{ url_for('employer_dashboard') }}#jobs" class="nav-pill">Jobs</a>
        <a href="{{ url_for('employer_dashboard') }}#applications" class="nav-pill">Applications</a>
        <a href="{{ url_for('employer_messages_page') }}" class="nav-pill active">Messages</a>
        <a href="{{ url_for('logout') }}" class="nav-pill">Logout</a>
    </div>"""

nav_links_replacement = """    <ul class="nav-links">
        <li><a href="{{ url_for('employer_dashboard') }}" class="nav-pill">My Jobs</a></li>
        <li><a href="{{ url_for('employer_jobposting_page') }}" class="nav-pill">Post a Job</a></li>
        <li><a href="{{ url_for('employer_top_candidates_page') }}" class="nav-pill">Top Candidates</a></li>
        <li><a href="{{ url_for('employer_applications_page') }}" class="nav-pill">Applications</a></li>
        <li><a href="{{ url_for('employer_messages_page') }}" class="nav-pill active">Messages</a></li>
    </ul>
    <a class="nav-avatar" href="{{ url_for('employer_dashboard') }}" title="Employer Dashboard" style="width: 40px; height: 40px; border-radius: 11px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.03); color: var(--text); display: inline-flex; align-items: center; justify-content: center; font-size: 14px; text-decoration: none; transition: all 0.2s ease;">
        <i class="fa-solid fa-user-gear"></i>
    </a>"""

html = html.replace(nav_links_target, nav_links_replacement)

# Replace Mobile media query to match other employer dashboard nav layouts
mobile_target = """        @media (max-width: 760px) {
            nav { height: auto; padding: 10px; flex-direction: column; gap: 10px; }
            .nav-links { flex-wrap: wrap; justify-content: center; margin-bottom: 5px; }
            .convo-list { width: 100%; border-right: none; background: var(--surface); }
            .chat-layout.chat-active .convo-list { display: none; }
            .chat-layout:not(.chat-active) .chat-area { display: none; }
            .chat-area { height: 100%; }
        }"""

mobile_replacement = """        @media (max-width: 980px) {
            nav { height: auto; padding: 10px 14px; display: grid; grid-template-columns: 1fr auto; grid-template-areas: "brand avatar" "links links"; align-items: center; row-gap: 10px; }
            .brand { grid-area: brand; min-width: 0; }
            .nav-avatar { grid-area: avatar; }
            .nav-links { grid-area: links; display: flex; gap: 8px; overflow-x: auto; white-space: nowrap; padding-bottom: 2px; scrollbar-width: none; flex-direction: row; }
            .nav-links::-webkit-scrollbar { display: none; }

            .convo-list { width: 100%; border-right: none; background: var(--surface); }
            .chat-layout.chat-active .convo-list { display: none; }
            .chat-layout:not(.chat-active) .chat-area { display: none !important; }
            .chat-area { height: 100%; }
        }"""

html = html.replace(mobile_target, mobile_replacement)

with open('templates/massage.html', 'w', encoding='utf-8') as f:
    f.write(html)
