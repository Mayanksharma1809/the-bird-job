import os
import re

template_dir = r"c:\Users\lenovo\OneDrive\Desktop\THEbirdJOB\templates"

for filename in os.listdir(template_dir):
    if filename.endswith(".html"):
        filepath = os.path.join(template_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Fix malformed linear-gradient replacements
        # E.g., background: transparent, #ffb347); 
        # Or background: transparent, var(--accent-2));
        new_content = re.sub(
            r'background:\s*transparent\s*,\s*[^;]+;',
            'background: transparent;',
            content
        )

        if new_content != content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Fixed {filename}")
