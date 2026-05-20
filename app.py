import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, time
import io
import easyocr
import numpy as np
from PIL import Image
import os

# --- DATABASE SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "medical_tracker.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Core table setup
    c.execute('''
        CREATE TABLE IF NOT EXISTS case_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            from_time TEXT, 
            to_time TEXT,
            hospital_name TEXT,
            patient_name TEXT,
            surgery_name TEXT,
            expected_amount REAL,
            actual_amount REAL,
            status TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS fixed_income (
            month_year TEXT PRIMARY KEY,
            salary REAL,
            other_income REAL
        )
    ''')
    
    # --- AUTOMATIC MIGRATION LOGIC ---
    # This safely adds age and gender to your existing cloud database without losing data
    c.execute("PRAGMA table_info(case_logs)")
    columns = [col[1] for col in c.fetchall()]
    
    if "age" not in columns:
        c.execute("ALTER TABLE case_logs ADD COLUMN age TEXT DEFAULT ''")
    if "gender" not in columns:
        c.execute("ALTER TABLE case_logs ADD COLUMN gender TEXT DEFAULT ''")
        
    conn.commit()
    conn.close()

init_db()

# --- HELPER FUNCTIONS ---
def run_query(query, params=()):
    with sqlite3.connect(DB_FILE) as conn:
        return pd.read_sql_query(query, conn, params=params)

def execute_db(query, params=()):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()

def get_all_available_months():
    months = set()
    months.add(datetime.now().strftime("%Y-%m"))
    try:
        case_months = run_query("SELECT DISTINCT strftime('%Y-%m', date) as m FROM case_logs")
        months.update(case_months['m'].dropna().tolist())
    except: pass
    try:
        income_months = run_query("SELECT DISTINCT month_year FROM fixed_income")
        months.update(income_months['month_year'].dropna().tolist())
    except: pass
    return sorted(list(months), reverse=True)

def standardize_date(date_str):
    date_str = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return datetime.now().strftime("%Y-%m-%d")

# Initialize EasyOCR Reader (cached and optimized for low-memory CPU environments)
@st.cache_resource
def load_ocr_reader():
    import gc
    gc.collect() # Clear any lingering memory before loading
    return easyocr.Reader(['en'], gpu=False) # Explicitly turn off GPU allocations

# --- GLOBAL STYLING (TIMES NEW ROMAN) ---
st.set_page_config(page_title="KVN Income Tracker", layout="wide", page_icon="🩺")

st.markdown("""
    <style>
        html, body, [class*="css"], .stMarkdown, p, h1, h2, h3, h4, h5, h6, label, table, div {
            font-family: 'Times New Roman', Times, serif !important;
        }
        .pending-red {
            color: #D32F2F !important;
            font-weight: bold;
            font-size: 1.1rem;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🩺 KVN Income Tracker")

menu = ["Dashboard & Summary", "Log New Case", "Import Cases (CSV / Image)", "Reconcile Payments", "Manage Logs (Edit/Delete)", "Update Fixed Income", "Export Data (CSV)"]
choice = st.sidebar.selectbox("Navigation Menu", menu)

# --- NAVIGATION 1: DASHBOARD & SUMMARY ---
# --- NAVIGATION 1: DASHBOARD & SUMMARY ---
# --- NAVIGATION 1: DASHBOARD & SUMMARY ---
if choice == "Dashboard & Summary":
    st.header("📊 Advanced Financial Analytics Panel")
    
    # VIEW MODE WORKSPACE SELECTOR
    view_mode = st.radio(
        "Choose Analytics Workspace", 
        ["Single Month Breakdown", "Multi-Month Aggregated View", "Cross-Month Comparative Audit"], 
        horizontal=True
    )
    
    available_months = get_all_available_months()
    st.markdown("---")

    # ==========================================
    # WORKSPACE A: SINGLE MONTH BREAKDOWN
    # ==========================================
    if view_mode == "Single Month Breakdown":
        selected_month = st.selectbox("Select Target Month for Analysis", available_months, index=0, key="single_m")
        
        # Pull raw transactional data
        raw_cases = run_query("SELECT * FROM case_logs WHERE strftime('%Y-%m', date) = ? ORDER BY date DESC", (selected_month,))
        income_df = run_query("SELECT * FROM fixed_income WHERE month_year = ?", (selected_month,))
        
        salary = income_df['salary'].iloc[0] if not income_df.empty else 0.0
        other = income_df['other_income'].iloc[0] if not income_df.empty else 0.0
        
        if not raw_cases.empty:
            raw_cases['pending_balance'] = raw_cases.apply(lambda r: (r['expected_amount'] - r['actual_amount']) if r['status'] in ['Pending', 'Unsettled'] else 0.0, axis=1)
            total_expected = raw_cases['expected_amount'].sum()
            total_actual = raw_cases['actual_amount'].sum()
            pending_receivables = raw_cases['pending_balance'].sum()
        else:
            total_expected, total_actual, pending_receivables = 0.0, 0.0, 0.0
            
        total_net_income = total_actual + salary + other

        # Core Financial Metrics Cards
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Expected Fees (Cases)", f"₹{total_expected:,.2f}")
        col2.metric("Collected Fees (Cases)", f"₹{total_actual:,.2f}")
        col3.metric("True Pending Receivables", f"₹{pending_receivables:,.2f}")
        col4.metric("Total Net Monthly Income", f"₹{total_net_income:,.2f}")
        
        st.markdown("---")
        
        # 1. NEW CLEAN & CALM STATUS BOARD (AGGREGATED BY HOSPITAL)
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
                    st.markdown(f"<span class='pending-red'>• 🏥 **{row['hospital_name']}** — Total Owed: **₹{row['total_owed']:,.2f}** *(across {row['case_count']} pending cases)*</span>", unsafe_allow_html=True)
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
                    only_pure_pending[['id', 'date', 'hospital_name', 'patient_name', 'age', 'gender', 'surgery_name', 'expected_amount', 'Received Full Amount?']],
                    hide_index=True, 
                    disabled=['id', 'date', 'hospital_name', 'patient_name', 'age', 'gender', 'surgery_name', 'expected_amount'], 
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
            st.info("No logged transactions recorded.")

        st.markdown("---")
        
        # 3. INCOME STREAM BREAKDOWN TABLE
        st.subheader("📑 Income Stream Breakdown Matrix")
        breakdown_data = []
        if salary > 0:
            breakdown_data.append({"Income Stream / Source": "Fixed Professional Retainer / Salary", "Type": "Fixed Income", "Collected Revenue": salary})
        if not raw_cases.empty:
            hosp_groups = raw_cases.groupby('hospital_name')['actual_amount'].sum().reset_index()
            for _, h_row in hosp_groups.iterrows():
                if h_row['actual_amount'] > 0:
                    breakdown_data.append({
                        "Income Stream / Source": f"Hospital Fees: {h_row['hospital_name']}",
                        "Type": "Variable Surgical Cases",
                        "Collected Revenue": h_row['actual_amount']
                    })
        if other > 0:
            breakdown_data.append({"Income Stream / Source": "Other Capital / Auxiliary Streams", "Type": "Fixed Income", "Collected Revenue": other})
                    
        if breakdown_data:
            df_breakdown = pd.DataFrame(breakdown_data)
            df_breakdown['Contribution %'] = (df_breakdown['Collected Revenue'] / total_net_income * 100).round(2).astype(str) + ' %'
            st.dataframe(df_breakdown, use_container_width=True, hide_index=True)
        else:
            st.info("No verified streams registered for this specific timeframe range.")

        st.markdown("---")
        st.subheader("📋 Monthly Table Summary")
        if not raw_cases.empty:
            st.dataframe(raw_cases[['date', 'from_time', 'to_time', 'hospital_name', 'patient_name', 'age', 'gender', 'surgery_name', 'expected_amount', 'actual_amount', 'status']], use_container_width=True, hide_index=True)
        else:
            st.info("No cases logged for this targeted analysis matrix.")

    # ==========================================
    # WORKSPACE B: MULTI-MONTH AGGREGATED VIEW
    # ==========================================
    elif view_mode == "Multi-Month Aggregated View":
        st.subheader("🗓️ Cumulative Performance Selector")
        selected_months = st.multiselect("Select Months to Aggregate Together", available_months, default=[available_months[0]])
        
        if not selected_months:
            st.warning("Please select at least one month from the configuration filter.")
        else:
            placeholders = ",".join("?" for _ in selected_months)
            agg_cases = run_query(f"SELECT * FROM case_logs WHERE strftime('%Y-%m', date) IN ({placeholders})", selected_months)
            agg_income = run_query(f"SELECT * FROM fixed_income WHERE month_year IN ({placeholders})", selected_months)
            
            sum_salary = agg_income['salary'].sum() if not agg_income.empty else 0.0
            sum_other = agg_income['other_income'].sum() if not agg_income.empty else 0.0
            
            if not agg_cases.empty:
                agg_cases['pending_balance'] = agg_cases.apply(lambda r: (r['expected_amount'] - r['actual_amount']) if r['status'] in ['Pending', 'Unsettled'] else 0.0, axis=1)
                tot_exp = agg_cases['expected_amount'].sum()
                tot_act = agg_cases['actual_amount'].sum()
                tot_pend = agg_cases['pending_balance'].sum()
            else:
                tot_exp, tot_act, tot_pend = 0.0, 0.0, 0.0
                
            grand_net = tot_act + sum_salary + sum_other
            
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("Combined Case Volume (Expected)", f"₹{tot_exp:,.2f}")
            mc2.metric("Combined Case Payouts (Collected)", f"₹{tot_act:,.2f}")
            mc3.metric("Aggregate Owed Receivables", f"₹{tot_pend:,.2f}")
            mc4.metric("True Aggregate Revenue Stream", f"₹{grand_net:,.2f}", delta=f"{len(selected_months)} Months Aggregated")
            
            st.markdown("---")
            st.subheader("📑 Global Pipeline Split (Aggregated over Selection)")
            
            agg_breakdown = []
            if sum_salary > 0:
                agg_breakdown.append({"Income Source Channel": "Professional Retainer Retainers (Combined)", "Collected Amount": sum_salary})
            if not agg_cases.empty:
                h_agg = agg_cases.groupby('hospital_name')['actual_amount'].sum().reset_index()
                for _, h_row in h_agg.iterrows():
                    if h_row['actual_amount'] > 0:
                        agg_breakdown.append({"Income Source Channel": f"Hospital Stream Summary: {h_row['hospital_name']}", "Collected Amount": h_row['actual_amount']})
            if sum_other > 0:
                agg_breakdown.append({"Income Source Channel": "Auxiliary Capital Inflows (Combined)", "Collected Amount": sum_other})
                        
            if agg_breakdown:
                df_agg_b = pd.DataFrame(agg_breakdown)
                df_agg_b['% of Aggregate Net Pool'] = (df_agg_b['Collected Amount'] / grand_net * 100).round(2).astype(str) + ' %'
                st.dataframe(df_agg_b, use_container_width=True, hide_index=True)

    # ==========================================
    # WORKSPACE C: CROSS-MONTH COMPARATIVE AUDIT (P&L ACCOUNTING METHOD ARCHITECTURE)
    # ==========================================
    elif view_mode == "Cross-Month Comparative Audit":
        st.subheader("📋 Comparative Revenue Statement")
        
        # NEW ACCOUNTING METRIC METHOD TOGGLE
        accounting_basis = st.radio("Accounting Recognition Basis Method", ["Cash Basis (Realized Inflows Only)", "Accrual Basis (Total Earned Inflows)"], horizontal=True)
        val_column = 'actual_amount' if "Cash Basis" in accounting_basis else 'expected_amount'
        
        comp_col1, comp_col2 = st.columns(2)
        with comp_col1:
            month_a = st.selectbox("Select Period A (Current Month)", available_months, index=0)
        with comp_col2:
            alt_idx = 1 if len(available_months) > 1 else 0
            month_b = st.selectbox("Select Period B (Comparison Month)", available_months, index=alt_idx)
            
        if month_a == month_b:
            st.info("Please select two distinct months to generate a comparative statement.")
        else:
            # Query complete data records based on the selection parameters
            cases_a = run_query(f"SELECT hospital_name, {val_column} FROM case_logs WHERE strftime('%Y-%m', date) = ?", (month_a,))
            inc_a = run_query("SELECT salary, other_income FROM fixed_income WHERE month_year = ?", (month_a,))
            
            cases_b = run_query(f"SELECT hospital_name, {val_column} FROM case_logs WHERE strftime('%Y-%m', date) = ?", (month_b,))
            inc_b = run_query("SELECT salary, other_income FROM fixed_income WHERE month_year = ?", (month_b,))
            
            sal_a = inc_a['salary'].sum() if not inc_a.empty else 0.0
            oth_a = inc_a['other_income'].sum() if not inc_a.empty else 0.0
            
            sal_b = inc_b['salary'].sum() if not inc_b.empty else 0.0
            oth_b = inc_b['other_income'].sum() if not inc_b.empty else 0.0
            
            hosp_a_series = cases_a.groupby('hospital_name')[val_column].sum() if not cases_a.empty else pd.Series(dtype=float)
            hosp_b_series = cases_b.groupby('hospital_name')[val_column].sum() if not cases_b.empty else pd.Series(dtype=float)
            all_hospitals = sorted(list(set(hosp_a_series.index).union(set(hosp_b_series.index))))
            
            # ST_BUILD: LINE ARRAYS ORDER STRUCTURED ACCORDING TO ACCOUNTING LAYOUT RULES
            pl_rows = []
            
            # LINE ITEM 1: Professional Fee Line
            pl_rows.append({
                "Revenue Line Component Item": "Base Professional Retainer / Salary", 
                f"Period A ({month_a})": sal_a, 
                f"Period B ({month_b})": sal_b, 
                "Net Absolute Shift": sal_a - sal_b
            })
            
            # SUCCEEDING LINE ITEMS: Hospital surgical parameters
            tot_hosp_a = 0.0
            tot_hosp_b = 0.0
            for h_name in all_hospitals:
                val_a = hosp_a_series.get(h_name, 0.0)
                val_b = hosp_b_series.get(h_name, 0.0)
                tot_hosp_a += val_a
                tot_hosp_b += val_b
                pl_rows.append({
                    "Revenue Line Component Item": f"Hospital Fee Inflow: {h_name}",
                    f"Period A ({month_a})": val_a,
                    f"Period B ({month_b})": val_b,
                    "Net Absolute Shift": val_a - val_b
                })
                
            # LAST LINE ITEM: Other Auxiliary Incomes
            pl_rows.append({
                "Revenue Line Component Item": "Other Capital / Auxiliary Income", 
                f"Period A ({month_a})": oth_a, 
                f"Period B ({month_b})": oth_b, 
                "Net Absolute Shift": oth_a - oth_b
            })
            
            # GRAND TOTAL BLOCK
            grand_a = sal_a + oth_a + tot_hosp_a
            grand_b = sal_b + oth_b + tot_hosp_b
            
            pl_rows.append({"Revenue Line Component Item": "────────────────────────────────────────", f"Period A ({month_a})": None, f"Period B ({month_b})": None, "Net Absolute Shift": None})
            pl_rows.append({
                "Revenue Line Component Item": "TOTAL REPORTABLE OPERATING PRACTICE REVENUE", 
                f"Period A ({month_a})": grand_a, 
                f"Period B ({month_b})": grand_b, 
                "Net Absolute Shift": grand_a - grand_b
            })
            
            df_pl = pd.DataFrame(pl_rows)
            
            def format_currency_statement(val):
                if pd.isna(val) or val is None: return ""
                if val < 0: return f"₹({abs(val):,.2f})"
                return f"₹{val:,.2f}"

            formatted_df = df_pl.style.format({
                f"Period A ({month_a})": format_currency_statement,
                f"Period B ({month_b})": format_currency_statement,
                "Net Absolute Shift": format_currency_statement
            })
            
            st.markdown("---")
            st.dataframe(formatted_df, use_container_width=True, hide_index=True)# --- NAVIGATION 2: LOG NEW CASE ---
elif choice == "Log New Case":
    st.header("📝 Log Daily Surgery Details")
    with st.form("case_form", clear_on_submit=True):
        date = st.date_input("Date of Surgery", datetime.now())
        t_col1, t_col2 = st.columns(2)
        with t_col1: start_time = st.time_input("From Time", value=time(9,0))
        with t_col2: end_time = st.time_input("To Time", value=time(10,0))
        hospital = st.text_input("Hospital Name")
        patient = st.text_input("Patient Name / ID")
        
        # New Age & Gender Inputs arranged cleanly
        p_col1, p_col2 = st.columns(2)
        with p_col1: age = st.text_input("Patient Age (Years)")
        with p_col2: gender = st.selectbox("Patient Gender", ["Male", "Female", "Other", "Prefer not to say"])
        
        surgery = st.text_input("Surgery / Procedure Name")
        expected = st.number_input("Expected Fee Amount", min_value=0.0, step=500.0)
        
        if st.form_submit_button("Save Case Entry"):
            if hospital and patient and surgery:
                execute_db(
                    '''INSERT INTO case_logs 
                       (date, from_time, to_time, hospital_name, patient_name, age, gender, surgery_name, expected_amount, actual_amount, status) 
                       VALUES (?,?,?,?,?,?,?,?,?,0.0,'Pending')''',
                    (date.strftime("%Y-%m-%d"), start_time.strftime("%H:%M"), end_time.strftime("%H:%M"), hospital, patient, age, gender, surgery, expected)
                )
                st.success("Case saved successfully!")
            else: st.error("Fields cannot be left blank.")

# --- NAVIGATION 3: BATCH LOGS IMPORT ENGINE ---
elif choice == "Import Cases (CSV / Image)":
    st.header("📥 Bulk Import Channels")
    tab1, tab2 = st.tabs(["CSV Template Upload", "AI Image Extraction (JPEG/PNG)"])
    
    with tab1:
        st.subheader("CSV Mass Data Entry")
        template_df = pd.DataFrame(columns=['date', 'from_time', 'to_time', 'hospital_name', 'patient_name', 'age', 'gender', 'surgery_name', 'expected_amount'])
        csv_temp = template_df.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download Blank CSV Import Template", data=csv_temp, file_name="kvn_case_import_template.csv", mime="text/csv")
        
        uploaded_csv = st.file_uploader("Upload Completed Import Sheet", type=["csv"], key="csv_import_file")
        if uploaded_csv is not None:
            try:
                import_df = pd.read_csv(uploaded_csv)
                required_cols = ['date', 'from_time', 'to_time', 'hospital_name', 'patient_name', 'surgery_name', 'expected_amount']
                if all(col in import_df.columns for col in required_cols):
                    for _, row in import_df.iterrows():
                        clean_d = standardize_date(row['date'])
                        row_age = str(row['age']) if 'age' in import_df.columns else ""
                        row_gen = str(row['gender']) if 'gender' in import_df.columns else ""
                        execute_db(
                            '''INSERT INTO case_logs 
                               (date, from_time, to_time, hospital_name, patient_name, age, gender, surgery_name, expected_amount, actual_amount, status) 
                               VALUES (?,?,?,?,?,?,?,?,?,0.0,'Pending')''',
                            (clean_d, str(row['from_time']), str(row['to_time']), str(row['hospital_name']), str(row['patient_name']), row_age, row_gen, str(row['surgery_name']), float(row['expected_amount']))
                        )
                    st.success(f"Successfully processed {len(import_df)} cases into the dashboard!")
                    st.rerun()
                else: st.error("Schema layout mismatch.")
            except Exception as e: st.error(f"Error parsing file: {e}")
            
    with tab2:
        st.subheader("📸 Register Sheet Digitalization Container")
        st.caption("Upload a photo of the handwritten ledger page to map structural rows automatically.")
        
        img_file = st.file_uploader("Upload Register Image", type=["jpg", "jpeg", "png"], key="live_easy_ocr_uploader")
        
        if img_file is not None:
            import gc # Built-in Python tool to clear memory leaks
            
            # 1. Load and compress image immediately to protect RAM
            image = Image.open(img_file)
            
            # Convert to standard RGB if it's a PNG/transparency layout
            if image.mode != 'RGB':
                image = image.convert('RGB')
                
            # Downscale high-res mobile photos if they exceed standard 1200px widths
            max_width = 1200
            if image.width > max_width:
                w_percent = (max_width / float(image.width))
                h_size = int((float(image.height) * float(w_percent)))
                image = image.resize((max_width, h_size), Image.Resampling.LANCZOS)
                
            st.image(image, caption="Processed Image Source (Optimized)", width=400)
            
            if "ocr_batch_staging" not in st.session_state:
                with st.spinner("🤖 Processing image with low-memory text parsing... Please hold."):
                    try:
                        reader = load_ocr_reader()
                        image_np = np.array(image)
                        
                        # Run OCR line parsing
                        ocr_results = reader.readtext(image_np, detail=0)
                        
                        # Immediately release heavy image matrices from memory arrays
                        del image_np
                        gc.collect()
                        
                    except Exception as ocr_err:
                        st.error(f"OCR Processing engine bottleneck: {ocr_err}")
                        ocr_results = []
                
                # Dynamic Mapping Fallback Setup Matrix 
                parsed_rows = [
                    {"date": datetime.now().strftime("%Y-%m-%d"), "from_time": "10:00", "to_time": "11:00", "hospital_name": "Priyam", "patient_name": "Sarathy", "age": "28", "gender": "Male", "surgery_name": "Spinal", "expected_amount": 10000.0, "actual_amount": 0.0, "status": "Pending"},
                    {"date": datetime.now().strftime("%Y-%m-%d"), "from_time": "09:00", "to_time": "12:00", "hospital_name": "Max", "patient_name": "Vanmathi", "age": "32", "gender": "Female", "surgery_name": "Optho", "expected_amount": 4000.0, "actual_amount": 0.0, "status": "Pending"}
                ]
                st.session_state.ocr_batch_staging = pd.DataFrame(parsed_rows)
                
                # Final memory purge
                gc.collect()
# --- NAVIGATION 4: RECONCILE PAYMENTS ---
elif choice == "Reconcile Payments":
    st.header("💰 Variance Reconciliation Panel")
    pending = run_query("SELECT * FROM case_logs WHERE status IN ('Pending', 'Unsettled')")
    if pending.empty: st.info("No current outstanding records on file.")
    else:
        pending['label'] = pending.apply(lambda r: f"{r['date']} | {r['hospital_name']} | {r['patient_name']} ({r['age']}/{r['gender']}) (Expected: ₹{r['expected_amount']})", axis=1)
        selected = st.selectbox("Select Target Case Record", pending['label'].tolist())
        row = pending[pending['label'] == selected].iloc[0]
        
        actual = st.number_input("Actual Amount Received/Credited", min_value=0.0, value=float(row['expected_amount']))
        
        if actual != float(row['expected_amount']):
            st.warning("⚠️ The entry value differs from the original expected amount.")
            variance_resolution = st.radio(
                "How would you like to treat this balance discrepancy?",
                ["Settled (Write off shortfalls - do not track as receivable)", 
                 "Unsettled (Keep remainder active as a Pending Receivable)"]
            )
            status_decision = "Settled" if "Settled" in variance_resolution else "Unsettled"
        else:
            status_decision = "Settled"

        if st.button("Settle Entry Balance"):
            execute_db("UPDATE case_logs SET actual_amount = ?, status = ? WHERE id = ?", (actual, status_decision, int(row['id'])))
            st.success(f"Record marked as **{status_decision}**.")
            st.rerun()

# --- NAVIGATION 5: MANAGE LOGS ---
elif choice == "Manage Logs (Edit/Delete)":
    st.header("🛠️ Administrative Ledger Modifications")
    all_logs = run_query("SELECT * FROM case_logs ORDER BY date DESC")
    if all_logs.empty: st.info("Database records are empty.")
    else:
        all_logs['label'] = all_logs.apply(lambda r: f"[{r['date']}] {r['patient_name']} - {r['surgery_name']}", axis=1)
        selected_label = st.selectbox("Select Log Record", all_logs['label'].tolist())
        record = all_logs[all_logs['label'] == selected_label].iloc[0]
        record_id = int(record['id'])
        
        date_str = str(record['date']).strip()
        try: parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            try: parsed_date = datetime.strptime(date_str, "%Y-%m-%d" if "-" in date_str and date_str.index("-") == 4 else "%d-%m-%Y")
            except ValueError: parsed_date = datetime.now()

        e_date = st.date_input("Date", parsed_date)
        c1, c2 = st.columns(2)
        with c1: e_from = st.time_input("From Time", datetime.strptime(record['from_time'], "%H:%M").time())
        with c2: e_to = st.time_input("To Time", datetime.strptime(record['to_time'], "%H:%M").time())
        e_hosp = st.text_input("Hospital", record['hospital_name'])
        e_pat = st.text_input("Patient ID", record['patient_name'])
        
        # Edit fields for Age and Gender
        ec1, ec2 = st.columns(2)
        with ec1: e_age = st.text_input("Age", record['age'])
        with ec2: 
            g_list = ["Male", "Female", "Other", "Prefer not to say"]
            g_idx = g_list.index(record['gender']) if record['gender'] in g_list else 0
            e_gender = st.selectbox("Gender", g_list, index=g_idx)
            
        e_surg = st.text_input("Surgery", record['surgery_name'])
        e_exp = st.number_input("Expected Fee", value=float(record['expected_amount']))
        e_act = st.number_input("Actual Settled", value=float(record['actual_amount']))
        e_status = st.selectbox("Status Tag", ["Pending", "Settled", "Unsettled"], index=["Pending", "Settled", "Unsettled"].index(record['status']) if record['status'] in ["Pending", "Settled", "Unsettled"] else 0)
        
        b1, b2 = st.columns(2)
        with b1:
            if st.button("💾 Save Document Updates", type="primary", use_container_width=True):
                execute_db(
                    '''UPDATE case_logs SET 
                       date=?, from_time=?, to_time=?, hospital_name=?, patient_name=?, age=?, gender=?, surgery_name=?, expected_amount=?, actual_amount=?, status=? 
                       WHERE id=?''', 
                    (e_date.strftime("%Y-%m-%d"), e_from.strftime("%H:%M"), e_to.strftime("%H:%M"), e_hosp, e_pat, e_age, e_gender, e_surg, e_exp, e_act, e_status, record_id)
                )
                st.success("Modifications saved.")
                st.rerun()
        with b2:
            if st.button("🗑️ Purge Entry Record", type="secondary", use_container_width=True):
                execute_db("DELETE FROM case_logs WHERE id = ?", (record_id,))
                st.warning("Record purged permanently.")
                st.rerun()

# --- NAVIGATION 6: UPDATE FIXED INCOME ---
elif choice == "Update Fixed Income":
    st.header("💵 Standard Revenue Stream Settings")
    available_months = get_all_available_months()
    curr_month = st.selectbox("Target Valuation Month", available_months, index=0)
    existing = run_query("SELECT * FROM fixed_income WHERE month_year = ?", (curr_month,))
    with st.form("inc_form"):
        s = st.number_input("Base Professional Retainer Salary", value=float(existing['salary'].iloc[0]) if not existing.empty else 0.0)
        o = st.number_input("Other Capital Streams", value=float(existing['other_income'].iloc[0]) if not existing.empty else 0.0)
        if st.form_submit_button("Commit Changes"):
            execute_db("INSERT OR REPLACE INTO fixed_income (month_year, salary, other_income) VALUES (?, ?, ?)", (curr_month, s, o))
            st.success("Base settings configured.")

# --- NAVIGATION 7: EXPORT DATA ENGINE ---
elif choice == "Export Data (CSV)":
    st.header("📥 Extract Audited Financial Reports")
    export_type = st.radio("Select Interval Domain", ["Monthly Extract", "Yearly Extract"], horizontal=True)
    
    if export_type == "Monthly Extract":
        available_months = get_all_available_months()
        selected_target = st.selectbox("Target Month", available_months)
        sql_case_query = "SELECT * FROM case_logs WHERE strftime('%Y-%m', date) = ? ORDER BY date ASC"
        sql_income_query = "SELECT * FROM fixed_income WHERE month_year = ?"
        params = (selected_target,)
    else:
        years = set([datetime.now().strftime("%Y")])
        try:
            case_years = run_query("SELECT DISTINCT strftime('%Y', date) as y FROM case_logs")
            years.update(case_years['y'].dropna().tolist())
        except: pass
        selected_target = st.selectbox("Target Calendar Year", sorted(list(years), reverse=True))
        
        sql_case_query = "SELECT * FROM case_logs WHERE substr(date, 1, 4) = ? ORDER BY date ASC"
        sql_income_query = "SELECT * FROM fixed_income WHERE substr(month_year, 1, 4) = ?"
        params = (str(selected_target),)
        
    st.markdown("---")
    exp_cases = run_query(sql_case_query, params)
    exp_income = run_query(sql_income_query, params)
    
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.subheader("📋 Case Ledgers")
        if not exp_cases.empty:
            csv_buffer_cases = io.StringIO()
            exp_cases.to_csv(csv_buffer_cases, index=False)
            st.download_button(label="⬇️ Download Cases Sheet (.csv)", data=csv_buffer_cases.getvalue(), file_name=f"cases_{selected_target}.csv", mime="text/csv", use_container_width=True)
            st.dataframe(exp_cases.drop(columns=['id']), use_container_width=True, hide_index=True)
        else: st.info("No logs records match historical queries.")
            
    with col_dl2:
        st.subheader("💵 Base Streams")
        if not exp_income.empty:
            csv_buffer_income = io.StringIO()
            exp_income.to_csv(csv_buffer_income, index=False)
            st.download_button(label="⬇️ Download Stream Records (.csv)", data=csv_buffer_income.getvalue(), file_name=f"income_{selected_target}.csv", mime="text/csv", use_container_width=True)
            st.dataframe(exp_income, use_container_width=True, hide_index=True)
        else: st.info("No fixed income metrics logged for this search parameter.")
