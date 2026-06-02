import re
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace any remaining f"₹{expr:,.2f}" or similar
content = re.sub(r'₹\{([^}]+):,\.2f\}', r'{format_inr(\1).replace("₹", "")}', content)
# Ensure we don't mess up if there's just `{expr:,.2f}` without ₹
content = re.sub(r'\{([^}]+):,\.2f\}', r'{format_inr(\1).replace("₹", "")}', content)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
