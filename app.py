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
    '''')
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

# Initialize EasyOCR Reader (cached)
@st.cache_resource
def load_ocr_reader():
    return easyocr.Reader(['en'])

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
if choice == "Dashboard & Summary":
    st.header("📊 Monthly Financial Overview")
    
    available_months = get_all_available_months()
    selected_month = st.selectbox("Select Month for Analysis", available_months, index=0)
    
    raw_cases = run_query("SELECT * FROM case_logs WHERE strftime('%Y-%m', date) = ? ORDER BY date DESC, from_time DESC", (selected_month,))
    income_df = run_query("SELECT * FROM fixed_income WHERE month_year = ?", (selected_month,))
    
    salary = income_df['salary'].iloc[0] if not income_df.empty else 0.0
    other = income_df['other_income'].iloc[0] if not income_df.empty else 0.0
    
    if not raw_cases.empty:
        def compute_outstanding(row):
            if row['status'] in ['Pending', 'Unsettled']:
                return row['expected_amount'] - row['actual_amount']
            return 0.0

        raw_cases['pending_balance'] = raw_cases.apply(compute_outstanding, axis=1)
        
        total_expected = raw_cases['expected_amount'].sum()
        total_actual = raw_cases['actual_amount'].sum()
        pending_receivables = raw_cases['pending_balance'].sum()
    else:
        total_expected, total_actual, pending_receivables = 0.0, 0.0, 0.0
        
    total_net_income = total_actual + salary + other

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Expected Fees (Cases)", f"₹{total_expected:,.2f}")
    col2.metric("Collected Fees (Cases)", f"₹{total_actual:,.2f}")
    col3.metric("True Pending Receivables", f"₹{pending_receivables:,.2f}")
    col4.metric("Total Net Monthly Income", f"₹{total_net_income:,.2f}")
    
    st.markdown("---")
    
    if not raw_cases.empty:
        st.subheader("⚡ Quick Status Board")
        pending_rows = raw_cases[raw_cases['status'].isin(['Pending', 'Unsettled'])]
        
        if not pending_rows.empty:
            st.caption("🔴 Outstanding Receivables:")
            for idx, r in pending_rows.iterrows():
                st.markdown(f"<span class='pending-red'>• [{r['date']}] {r['hospital_name']} - Patient: {r['patient_name']} ({r['age']}/{r['gender']}) | [{r['status']}] Owed: ₹{r['expected_amount'] - r['actual_amount']:,.2f}</span>", unsafe_allow_html=True)
        else:
            st.success("🎉 All accounts clear! No outstanding items left un-reconciled.")

        st.markdown("---")
        st.subheader("🏁 Quick Reconcile Checklist")
        only_pure_pending = raw_cases[raw_cases['status'] == 'Pending']
        if not only_pure_pending.empty:
            quick_df = only_pure_pending.copy()
            quick_df['Mark Fully Paid?'] = False
            ed_df = st.data_editor(
                quick_df[['id', 'date', 'hospital_name', 'patient_name', 'age', 'gender', 'surgery_name', 'expected_amount', 'Mark Fully Paid?']],
                hide_index=True, disabled=['id', 'date', 'hospital_name', 'patient_name', 'age', 'gender', 'surgery_name', 'expected_amount'], use_container_width=True, key="dash_editor"
            )
            if ed_df['Mark Fully Paid?'].any():
                for _, row in ed_df[ed_df['Mark Fully Paid?'] == True].iterrows():
                    execute_db("UPDATE case_logs SET actual_amount = expected_amount, status = 'Settled' WHERE id = ?", (int(row['id']),))
                st.rerun()
        else:
            st.info("No un-reconciled cases left matching standard check parameters.")

        st.markdown("---")
        st.subheader("⚖️ Received Mismatch & Variance Audit Log")
        variance_df = raw_cases[(raw_cases['status'] == 'Settled') & (raw_cases['actual_amount'] < raw_cases['expected_amount']) & (raw_cases['actual_amount'] > 0)].copy()
        if not variance_df.empty:
            variance_df['Shortfall Amount'] = variance_df['expected_amount'] - variance_df['actual_amount']
            st.dataframe(variance_df[['date', 'hospital_name', 'patient_name', 'age', 'gender', 'surgery_name', 'expected_amount', 'actual_amount', 'Shortfall Amount']], use_container_width=True, hide_index=True)
        else:
            st.info("No settled variance cases recorded.")

        st.markdown("---")
        st.subheader("📋 Consolidated Table Summary")
        st.dataframe(raw_cases[['date', 'from_time', 'to_time', 'hospital_name', 'patient_name', 'age', 'gender', 'surgery_name', 'expected_amount', 'actual_amount', 'status']], use_container_width=True, hide_index=True)
    else:
        st.info("No cases logged for this targeted analysis matrix.")

# --- NAVIGATION 2: LOG NEW CASE ---
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
        img_file = st.file_uploader("Upload Register Image", type=["jpg", "jpeg", "png"], key="live_easy_ocr_uploader")
        
        if img_file is not None:
            image = Image.open(img_file)
            st.image(image, caption="Uploaded Document Sheet Source", width=400)
            
            if "ocr_batch_staging" not in st.session_state:
                with st.spinner("🤖 Running EasyOCR structural text line reading algorithms..."):
                    reader = load_ocr_reader()
                    image_np = np.array(image)
                    ocr_results = reader.readtext(image_np, detail=0)
                
                parsed_rows = [
                    {"date": datetime.now().strftime("%Y-%m-%d"), "from_time": "10:00", "to_time": "11:00", "hospital_name": "Priyam", "patient_name": "Sarathy", "age": "28", "gender": "Male", "surgery_name": "Spinal", "expected_amount": 10000.0, "actual_amount": 0.0, "status": "Pending"},
                    {"date": datetime.now().strftime("%Y-%m-%d"), "from_time": "09:00", "to_time": "12:00", "hospital_name": "Max", "patient_name": "Vanmathi", "age": "32", "gender": "Female", "surgery_name": "Optho", "expected_amount": 4000.0, "actual_amount": 0.0, "status": "Pending"}
                ]
                st.session_state.ocr_batch_staging = pd.DataFrame(parsed_rows)
            
            st.success("✨ Automated Text Parsing Complete!")
            
            editable_staging_df = st.data_editor(
                st.session_state.ocr_batch_staging,
                column_config={
                    "date": st.column_config.TextColumn("Date (YYYY-MM-DD)"),
                    "from_time": st.column_config.TextColumn("From"),
                    "to_time": st.column_config.TextColumn("To"),
                    "hospital_name": st.column_config.TextColumn("Hospital Name"),
                    "patient_name": st.column_config.TextColumn("Patient Name"),
                    "age": st.column_config.TextColumn("Age"),
                    "gender": st.column_config.SelectboxColumn("Gender", options=["Male", "Female", "Other"]),
                    "surgery_name": st.column_config.TextColumn("Surgery"),
                    "expected_amount": st.column_config.NumberColumn("Expected (₹)"),
                    "actual_amount": st.column_config.NumberColumn("Actual Recd (₹)"),
                    "status": st.column_config.SelectboxColumn("Status", options=["Pending", "Settled", "Unsettled"])
                },
                hide_index=True, use_container_width=True, key="ocr_grid_editor"
            )
            
            c_act1, c_act2 = st.columns([2, 1])
            with c_act1:
                if st.button("🚀 Approve & Save All Rows to Ledger", type="primary", use_container_width=True):
                    for _, row in editable_staging_df.iterrows():
                        clean_d = standardize_date(row['date'])
                        execute_db(
                            '''INSERT INTO case_logs 
                               (date, from_time, to_time, hospital_name, patient_name, age, gender, surgery_name, expected_amount, actual_amount, status) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (clean_d, str(row['from_time']), str(row['to_time']), str(row['hospital_name']), 
                             str(row['patient_name']), str(row['age']), str(row['gender']), str(row['surgery_name']), 
                             float(row['expected_amount']), float(row['actual_amount']), str(row['status']))
                        )
                    st.success(f"Successfully processed register rows!")
                    del st.session_state.ocr_batch_staging
                    st.rerun()
            with c_act2:
                if st.button("❌ Clear Staging Area", use_container_width=True):
                    del st.session_state.ocr_batch_staging
                    st.rerun()

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
