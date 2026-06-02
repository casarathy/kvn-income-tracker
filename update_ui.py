import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add CSS for table headers
old_css = """        html, body, [class*="css"], .stMarkdown, p, h1, h2, h3, h4, h5, h6, label, table, div {
            font-family: 'Times New Roman', Times, serif !important;
        }"""
new_css = """        html, body, [class*="css"], .stMarkdown, p, h1, h2, h3, h4, h5, h6, label, table, div, [data-testid="stDataFrame"] * {
            font-family: 'Times New Roman', Times, serif !important;
        }
        [data-testid="stDataFrame"] div[role="columnheader"], [data-testid="stTable"] th {
            background-color: #4A90E2 !important;
            color: #ffffff !important;
            font-family: 'Times New Roman', Times, serif !important;
        }
        [data-testid="stDataFrame"] div[role="columnheader"] .st-emotion-cache-1zqw1ea, 
        [data-testid="stDataFrame"] div[role="columnheader"] div {
            color: #ffffff !important;
            font-family: 'Times New Roman', Times, serif !important;
        }"""
content = content.replace(old_css, new_css)

# 2. Replace Quick Status Board and Reconcile Checklist with the combined one
old_section_1 = """        # 1. NEW CLEAN & CALM STATUS BOARD (AGGREGATED BY HOSPITAL)
        st.subheader("⚡ Quick Status Board")
        if not raw_cases.empty and pending_receivables > 0:
            pending_cases = raw_cases[raw_cases['status'].isin(['Pending', 'Unsettled'])]
            if not pending_cases.empty:
                # Group by hospital name to show a clean aggregate summary loop
                hosp_summary = pending_cases.groupby('hospital_name').agg(
                    total_owed=('pending_balance', 'sum'),
                    case_count=('id', 'count')
                ).reset_index()
                
                st.caption("🔴 Outstanding Receivables by Facility:")
                for _, row in hosp_summary.iterrows():
                    st.markdown(f"<span class='pending-red'>• 🏥 **{row['hospital_name']}** — Total Owed: **{format_inr(row['total_owed'])}** *(across {row['case_count']} pending cases)*</span>", unsafe_allow_html=True)
        else:
            st.success("🎉 All accounts clear! No outstanding items left un-reconciled.")

        st.markdown("---")
        
        # 2. INSTANT "YES" QUICK RECONCILE CHECKLIST ON THE DASHBOARD
        st.subheader("🏁 Quick Reconcile Checklist")
        st.caption("Did you receive the exact expected amount? Toggle 'Yes' below to settle instantly.")
        if not raw_cases.empty:
            only_pure_pending = raw_cases[raw_cases['status'] == 'Pending'].copy()
            if not only_pure_pending.empty:
                only_pure_pending['Received Full Amount?'] = False
                
                # Render editable checklist data grid layout
                edited_checklist = st.data_editor(
                    only_pure_pending[['id', 'date', 'hospital_name', 'patient_name', 'age', 'gender', 'risk_profile', 'anaesthesia_type', 'surgery_name', 'expected_amount', 'Received Full Amount?']],
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
                    st.rerun()
            else:
                st.info("No un-reconciled cases left matching standard parameters.")
        else:
            st.info("No logged transactions recorded.")"""

new_section_1 = """        # 1. COMBINED INTERACTIVE STATUS & RECONCILE BOARD
        st.subheader("⚡ Interactive Quick Status & Reconcile Board")
        st.caption("Filter by any criteria. Toggle 'Received Full Amount?' to instantly settle pending accounts.")
        if not raw_cases.empty:
            only_pure_pending = raw_cases[raw_cases['status'].isin(['Pending', 'Unsettled'])].copy()
            if not only_pure_pending.empty:
                # Add filters
                st.markdown("##### 🔍 Filter & Search Cases")
                f_col1, f_col2, f_col3, f_col4 = st.columns(4)
                with f_col1:
                    hosp_filter = st.multiselect("🏥 Hospital", options=only_pure_pending['hospital_name'].unique())
                with f_col2:
                    risk_filter = st.multiselect("⚠️ Risk Profile", options=only_pure_pending['risk_profile'].unique())
                with f_col3:
                    anes_filter = st.multiselect("🏷️ Anaesthesia", options=only_pure_pending['anaesthesia_type'].unique())
                with f_col4:
                    surg_filter = st.multiselect("🔪 Surgery Name", options=only_pure_pending['surgery_name'].unique())
                
                filtered_df = only_pure_pending.copy()
                if hosp_filter:
                    filtered_df = filtered_df[filtered_df['hospital_name'].isin(hosp_filter)]
                if risk_filter:
                    filtered_df = filtered_df[filtered_df['risk_profile'].isin(risk_filter)]
                if anes_filter:
                    filtered_df = filtered_df[filtered_df['anaesthesia_type'].isin(anes_filter)]
                if surg_filter:
                    filtered_df = filtered_df[filtered_df['surgery_name'].isin(surg_filter)]
                
                filtered_df['Received Full Amount?'] = False
                
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
                    st.rerun()
            else:
                st.success("🎉 All accounts clear! No outstanding items left un-reconciled.")
        else:
            st.info("No logged transactions recorded.")"""

content = content.replace(old_section_1, new_section_1)

# 3. Remove Case Classifications Analytics entirely
old_section_2 = """        # 5. Surgery Classifications Analytics
        st.subheader("📈 Case Classifications Analytics")
        if not raw_cases.empty:
            sc_col1, sc_col2 = st.columns(2)
            with sc_col1:
                st.caption("Risk Profile Distribution")
                risk_counts = raw_cases['risk_profile'].value_counts().reset_index()
                risk_counts.columns = ['Risk Profile', 'Number of Cases']
                st.dataframe(risk_counts, use_container_width=True, hide_index=True)
            with sc_col2:
                st.caption("Anaesthesia Type Distribution")
                cat_counts = raw_cases['anaesthesia_type'].value_counts().reset_index()
                cat_counts.columns = ['Anaesthesia Type', 'Number of Cases']
                st.dataframe(cat_counts, use_container_width=True, hide_index=True)

        st.markdown("---")"""

content = content.replace(old_section_2, "")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Dashboard UI modified successfully.")
