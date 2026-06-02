import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

old_section = """                filtered_df['Received Full Amount?'] = False
                
                # Render editable checklist data grid layout
                edited_checklist = st.data_editor(
                    filtered_df[['id', 'date', 'hospital_name', 'patient_name', 'age', 'gender', 'risk_profile', 'anaesthesia_type', 'surgery_name', 'expected_amount', 'Received Full Amount?']],
                    hide_index=True, 
                    disabled=['id', 'date', 'hospital_name', 'patient_name', 'age', 'gender', 'risk_profile', 'anaesthesia_type', 'surgery_name', 'expected_amount'], 
                    use_container_width=True, 
                    key="quick_dash_settler"
                )
                
                # Check if any row was toggled to "Yes"
                if edited_checklist['Received Full Amount?'].any():
                    for _, row in edited_checklist[edited_checklist['Received Full Amount?'] == True].iterrows():
                        # Instantly update database setting actual_amount equal to expected_amount
                        execute_db(
                            "UPDATE case_logs SET actual_amount = expected_amount, status = 'Settled' WHERE id = ?", 
                            (int(row['id']),)
                        )
                    st.rerun()"""

new_section = """                def calc_hours(r):
                    try:
                        if pd.isna(r['from_time']) or pd.isna(r['to_time']): return 0.0
                        t1 = datetime.strptime(str(r['from_time']), "%H:%M")
                        t2 = datetime.strptime(str(r['to_time']), "%H:%M")
                        diff = (t2 - t1).total_seconds()
                        if diff < 0: diff += 86400
                        return diff / 3600.0
                    except:
                        return 0.0

                filtered_df['hours_worked'] = filtered_df.apply(calc_hours, axis=1)
                total_cases = len(filtered_df)
                total_amt = filtered_df['expected_amount'].sum()
                total_hrs = filtered_df['hours_worked'].sum()
                avg_per_case = total_amt / total_cases if total_cases > 0 else 0
                avg_per_hr = total_amt / total_hrs if total_hrs > 0 else 0

                st.markdown(f'''
                <div style="display: flex; gap: 15px; margin-top: 10px; margin-bottom: 25px; flex-wrap: wrap;">
                    <div style="flex: 1; background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; color: white;">
                        <h4 style="margin:0; font-size: 1.1rem; text-transform: uppercase;">Total Cases</h4>
                        <h2 style="margin: 10px 0 0 0; font-size: 2rem;">{total_cases}</h2>
                    </div>
                    <div style="flex: 1; background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; color: white;">
                        <h4 style="margin:0; font-size: 1.1rem; text-transform: uppercase;">Total Amount</h4>
                        <h2 style="margin: 10px 0 0 0; font-size: 2rem;">{format_inr(total_amt)}</h2>
                    </div>
                    <div style="flex: 1; background: linear-gradient(135deg, #ff9966 0%, #ff5e62 100%); padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; color: white;">
                        <h4 style="margin:0; font-size: 1.1rem; text-transform: uppercase;">Total Hours</h4>
                        <h2 style="margin: 10px 0 0 0; font-size: 2rem;">{total_hrs:.1f} hrs</h2>
                    </div>
                    <div style="flex: 1; background: linear-gradient(135deg, #834d9b 0%, #d04ed6 100%); padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; color: white;">
                        <h4 style="margin:0; font-size: 1.1rem; text-transform: uppercase;">Avg per Case</h4>
                        <h2 style="margin: 10px 0 0 0; font-size: 2rem;">{format_inr(avg_per_case)}</h2>
                    </div>
                    <div style="flex: 1; background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%); padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; color: white;">
                        <h4 style="margin:0; font-size: 1.1rem; text-transform: uppercase;">Avg / Hour</h4>
                        <h2 style="margin: 10px 0 0 0; font-size: 2rem;">{format_inr(avg_per_hr)}</h2>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
                
                table_html = '''
                <style>
                .premium-table {
                    width: 100%;
                    border-collapse: collapse;
                    font-family: 'Times New Roman', Times, serif;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.05);
                    border-radius: 8px;
                    overflow: hidden;
                    margin-bottom: 20px;
                }
                .premium-table th {
                    background-color: #4A90E2;
                    color: white;
                    padding: 12px 15px;
                    text-align: left;
                    font-size: 1.05rem;
                    font-weight: bold;
                }
                .premium-table td {
                    padding: 10px 15px;
                    border-bottom: 1px solid #e0e0e0;
                    color: #333;
                }
                .premium-table tr:nth-child(even) {
                    background-color: #f8f9fa;
                }
                .premium-table tr:hover {
                    background-color: #e2eeff;
                }
                </style>
                <table class="premium-table">
                    <thead>
                        <tr>
                            <th>ID</th><th>Date</th><th>Hospital</th><th>Patient</th><th>Age/Sex</th><th>Risk</th><th>Anaesthesia</th><th>Surgery</th><th>Expected</th>
                        </tr>
                    </thead>
                    <tbody>
                '''
                for _, r in filtered_df.iterrows():
                    table_html += f'''
                        <tr>
                            <td>{r['id']}</td><td>{r['date']}</td><td>{r['hospital_name']}</td><td>{r['patient_name']}</td>
                            <td>{r['age']} / {r['gender']}</td><td>{r['risk_profile']}</td><td>{r['anaesthesia_type']}</td>
                            <td>{r['surgery_name']}</td><td><b>{format_inr(r['expected_amount'])}</b></td>
                        </tr>
                    '''
                table_html += '</tbody></table>'
                st.markdown(table_html, unsafe_allow_html=True)

                st.markdown("#### ✅ Reconcile Selected Cases")
                cases_to_settle = st.multiselect("Select Case IDs that you have received the full amount for:", options=filtered_df['id'].tolist(), format_func=lambda x: f"Case #{x} - {filtered_df[filtered_df['id']==x]['patient_name'].values[0]}")
                if st.button("Mark as Settled", type="primary"):
                    if cases_to_settle:
                        for cid in cases_to_settle:
                            execute_db("UPDATE case_logs SET actual_amount = expected_amount, status = 'Settled' WHERE id = ?", (int(cid),))
                        st.success(f"Successfully settled {len(cases_to_settle)} cases!")
                        st.rerun()"""

if old_section in content:
    content = content.replace(old_section, new_section)
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("UI updated.")
else:
    print("Could not find section to replace.")
