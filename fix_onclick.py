import re

filepath = r'C:\Users\lenovo\OneDrive\Desktop\THEbirdJOB\templates\topcandidate.html'

with open(filepath, 'r', encoding='utf-8') as f:
    html = f.read()

# Fix all three podium cards: rank1, rank2, rank3
# The broken pattern looks like:
#   onclick="showToast('Viewing {{ cX.candidate_name | replace("'", "") }}\'s full profile...')"
# We replace it with a data-name attribute + viewProfile(this) call

for rank, cx in [('rank1', 'c1'), ('rank2', 'c2'), ('rank3', 'c3')]:
    # Use a regex that matches the whole onclick attr on the podium-card div
    pattern = (
        r'(<div class="podium-card ' + rank + r'") '
        r'onclick="showToast\([^)]*\)"'
    )
    replacement = (
        r'\1 data-name="{{ ' + cx + r'.candidate_name }}" onclick="viewProfile(this)"'
    )
    html, n = re.subn(pattern, replacement, html)
    print(f"  {rank}: {n} replacement(s) made")

# Add viewProfile() function before </script>
if 'function viewProfile' not in html:
    view_fn = """
    function viewProfile(el) {
      const name = el.getAttribute('data-name') || 'this candidate';
      showToast(`Viewing ${name}'s full profile...`);
    }"""
    html = html.replace('</script>', view_fn + '\n  </script>', 1)
    print("  viewProfile() function added")
else:
    print("  viewProfile() already present")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(html)

print("Done!")
