import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace all occurrences of f"₹{var:,.2f}" with format_inr(var)
content = re.sub(r'f"₹\{([a-zA-Z0-9_]+):,\.2f\}"', r'format_inr(\1)', content)

# Replace all f"{var:,.2f}" inside metrics delta? (not found, only f"₹{...}")

# format_currency_statement replacement
old_format = '''            def format_currency_statement(val):
                if pd.isna(val) or val is None: return ""
                if val < 0: return f"₹({abs(val):,.2f})"
                return f"₹{val:,.2f}"'''
new_format = '''            def format_currency_statement(val):
                if pd.isna(val) or val is None: return ""
                if val < 0: 
                    formatted = format_inr(abs(val))
                    return f"{formatted.replace('₹', '₹(')})"
                return format_inr(val)'''
content = content.replace(old_format, new_format)

# Other inline occurrences of ₹{var:,.2f}
content = re.sub(r'₹\{([a-zA-Z0-9_]+):,\.2f\}', r'{format_inr(\1).replace("₹", "")}', content)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Formatting updated.")
