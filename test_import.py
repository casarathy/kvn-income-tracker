import sqlite3
import pandas as pd
from datetime import datetime

DB_FILE = "medical_tracker.db"

def execute_db(query, params=()):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()
    print("Executed query")

def standardize_date(date_str):
    date_str = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return datetime.now().strftime("%Y-%m-%d")

import_df = pd.DataFrame([{
    'id': '', 'date': '2023-01-01', 'from_time': '10:00', 'to_time': '11:00',
    'hospital_name': 'Test Hosp', 'patient_name': 'Test Patient', 
    'surgery_name': 'Test Surg', 'expected_amount': '1000', 
    'actual_amount': '1000', 'status': 'Settled', 'age': '30',
    'gender': 'M', 'risk_profile': 'Low', 'anaesthesia_type': 'General'
}])

success_count = 0
for index, row in import_df.iterrows():
    if pd.isna(row['patient_name']) or str(row['patient_name']).strip() == "":
        continue
        
    clean_d = standardize_date(row['date'])
    row_age = str(row['age']) if 'age' in import_df.columns and not pd.isna(row['age']) else ""
    row_gen = str(row['gender']) if 'gender' in import_df.columns and not pd.isna(row['gender']) else ""
    row_risk = str(row['risk_profile']) if 'risk_profile' in import_df.columns and not pd.isna(row['risk_profile']) else "Low"
    
    def safe_float(val):
        if pd.isna(val) or str(val).strip() == "": return 0.0
        try:
            return float(str(val).replace(',', '').replace('$', '').replace(' ', '').strip())
        except ValueError:
            return 0.0
            
    exp_amt = safe_float(row['expected_amount'])
    act_amt = safe_float(row['actual_amount']) if 'actual_amount' in import_df.columns else 0.0
    stat = str(row['status']).strip() if 'status' in import_df.columns and not pd.isna(row['status']) else "Pending"
    
    row_cat = "General"
    is_update = False
    if 'id' in import_df.columns and not pd.isna(row['id']):
        try:
            row_id = int(float(row['id']))
            is_update = True
        except ValueError:
            is_update = False
            
    if is_update:
        execute_db(
            '''UPDATE case_logs 
               SET date=?, from_time=?, to_time=?, hospital_name=?, patient_name=?, age=?, gender=?, surgery_name=?, expected_amount=?, actual_amount=?, status=?, risk_profile=?, anaesthesia_type=?
               WHERE id=?''',
            (clean_d, str(row['from_time']), str(row['to_time']), str(row['hospital_name']), str(row['patient_name']), row_age, row_gen, str(row['surgery_name']), exp_amt, act_amt, stat, row_risk, row_cat, row_id)
        )
    else:
        execute_db(
            '''INSERT INTO case_logs 
               (date, from_time, to_time, hospital_name, patient_name, age, gender, surgery_name, expected_amount, actual_amount, status, risk_profile, anaesthesia_type) 
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (clean_d, str(row['from_time']), str(row['to_time']), str(row['hospital_name']), str(row['patient_name']), row_age, row_gen, str(row['surgery_name']), exp_amt, act_amt, stat, row_risk, row_cat)
        )
    success_count += 1
print("Success:", success_count)
