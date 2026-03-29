import os
import re

template_dir = r"c:\Users\lenovo\OneDrive\Desktop\THEbirdJOB\templates"
static_brand_dir = r"c:\Users\lenovo\OneDrive\Desktop\THEbirdJOB\static\brand"

os.makedirs(static_brand_dir, exist_ok=True)

favicon_tag = """    <link rel="icon" href="{{ url_for('static', filename='brand/logo.png') }}" type="image/png">\n"""
logo_content = """<img src="{{ url_for('static', filename='brand/logo.png') }}" alt="Logo" style="width: 100%; height: 100%; object-fit: cover; transform: scale(1.6); border-radius: inherit; pointer-events: none;">"""

modified_count = 0

for filename in os.listdir(template_dir):
    if filename.endswith(".html"):
        filepath = os.path.join(template_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        original_content = content

        # 1. Insert favicon before </head>
        if '<link rel="icon"' not in content and '</head>' in content:
            content = content.replace("</head>", favicon_tag + "</head>")
            
        # 2. Replace the old icon inside .brand-mark with the new image
        # It handles both <span class="brand-mark">....</span> and <div class="brand-mark">....</div>
        content = re.sub(
            r'(<(?:span|div)[^>]*class="\s*brand-mark\s*"[^>]*>)(.*?)(</(?:span|div)>)',
            r'\1' + logo_content + r'\3',
            content,
            flags=re.DOTALL
        )
        
        # Handle variations like <span class="brand-mark"> (without space padding check because regex was strict)
        content = re.sub(
            r'(<(?:span|div)[^>]*class="(?:[^"]*\s)?brand-mark(?:\s[^"]*)?"[^>]*>)(.*?)(</(?:span|div)>)',
            r'\1' + logo_content + r'\3',
            content,
            flags=re.DOTALL
        )
        
        # 3. Remove the aggressive background colors from .brand-mark CSS to let the logo shine
        content = re.sub(
            r'(\.brand-mark\s*{[^}]*?background\s*:\s*)linear-gradient\([^)]+\)',
            r'\1transparent',
            content
        )
        # Handle simple background rules
        content = re.sub(
            r'(\.brand-mark\s*{[^}]*?background\s*:\s*)[#a-zA-Z0-9]+',
            r'\1transparent',
            content
        )
        # Keep border/box layout but drop shadow
        content = re.sub(
            r'(\.brand-mark\s*{[^}]*?)box-shadow\s*:[^;]+;',
            r'\1box-shadow: none;',
            content
        )

        if content != original_content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            modified_count += 1

print(f"Updated {modified_count} HTML templates successfully.")
