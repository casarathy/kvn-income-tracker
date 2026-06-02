import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update the table headers
old_headers = "<th>ID</th><th>Date</th><th>Hospital</th><th>Patient</th><th>Age/Sex</th><th>Risk</th><th>Anaesthesia</th><th>Surgery</th><th>Expected</th>"
new_headers = "<th>ID</th><th>Date</th><th>Time</th><th>Hospital</th><th>Patient</th><th>Age/Sex</th><th>Risk</th><th>Anaesthesia</th><th>Surgery</th><th>Expected</th>"
content = content.replace(old_headers, new_headers)

# 2. Update the iteration loop to sort by ID, format the date, and merge times
old_loop = """                for _, r in filtered_df.iterrows():
                    table_html += f"<tr><td>{r['id']}</td><td>{r['date']}</td><td>{r['hospital_name']}</td><td>{r['patient_name']}</td><td>{r['age']} / {r['gender']}</td><td>{r['risk_profile']}</td><td>{r['anaesthesia_type']}</td><td>{r['surgery_name']}</td><td><b>{format_inr(r['expected_amount'])}</b></td></tr>"
"""

new_loop = """                filtered_df = filtered_df.sort_values(by='id', ascending=True)
                for _, r in filtered_df.iterrows():
                    try:
                        formatted_date = datetime.strptime(str(r['date']), "%Y-%m-%d").strftime("%d-%m-%y")
                    except:
                        formatted_date = str(r['date'])
                    
                    ft = str(r['from_time']) if pd.notna(r['from_time']) and str(r['from_time']).strip() else ""
                    tt = str(r['to_time']) if pd.notna(r['to_time']) and str(r['to_time']).strip() else ""
                    time_str = f"{ft}-{tt}" if ft or tt else "-"
                    
                    table_html += f"<tr><td>{r['id']}</td><td>{formatted_date}</td><td>{time_str}</td><td>{r['hospital_name']}</td><td>{r['patient_name']}</td><td>{r['age']} / {r['gender']}</td><td>{r['risk_profile']}</td><td>{r['anaesthesia_type']}</td><td>{r['surgery_name']}</td><td><b>{format_inr(r['expected_amount'])}</b></td></tr>"
"""

content = content.replace(old_loop, new_loop)

# Also ensure `filtered_df` multiselect uses the sorted IDs
# Actually, the multiselect options just use `filtered_df['id'].tolist()`, so if we sort it before the multiselect, it's perfect.
# The multiselect is currently below the loop, so it will inherit the sorted `filtered_df`!
# Let's verify if `cases_to_settle = st.multiselect(..., options=filtered_df['id'].tolist(), ...)` works smoothly. It does.

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Formatting applied successfully.")
