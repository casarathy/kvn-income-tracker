import re
with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix the HTML table string indentation
old_loop = '''                for _, r in filtered_df.iterrows():
                    table_html += f\'\'\'
                        <tr>
                            <td>{r['id']}</td><td>{r['date']}</td><td>{r['hospital_name']}</td><td>{r['patient_name']}</td>
                            <td>{r['age']} / {r['gender']}</td><td>{r['risk_profile']}</td><td>{r['anaesthesia_type']}</td>
                            <td>{r['surgery_name']}</td><td><b>{format_inr(r['expected_amount'])}</b></td>
                        </tr>
                    \'\'\'
                table_html += '</tbody></table>'
'''

new_loop = '''                for _, r in filtered_df.iterrows():
                    table_html += f"<tr><td>{r['id']}</td><td>{r['date']}</td><td>{r['hospital_name']}</td><td>{r['patient_name']}</td><td>{r['age']} / {r['gender']}</td><td>{r['risk_profile']}</td><td>{r['anaesthesia_type']}</td><td>{r['surgery_name']}</td><td><b>{format_inr(r['expected_amount'])}</b></td></tr>"
                table_html += '</tbody></table>'
'''

content = content.replace(old_loop, new_loop)

# Let's also fix the indentation for the table_html assignment itself, to prevent the entire table from becoming a code block!
old_table_start = '''                table_html = \'''
                <style>
                .premium-table {'''

new_table_start = '''                table_html = """
<style>
.premium-table {"""'''

content = content.replace(old_table_start, new_table_start)

# Clean up all leading whitespace for HTML tags within the table_html string definition
content = re.sub(r'                ([<.])', r'\1', content)

# Fix syntax error on line 561 from the user's manual change
old_line = 'if val < 0: return f"₹({format_inr(abs(val)).replace("₹", "")})"'
new_line = 'if val < 0: return f"₹({format_inr(abs(val)).replace(\'₹\', \'\')})"'
content = content.replace(old_line, new_line)


with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Indentation fixed.")
