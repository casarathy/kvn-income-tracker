import sqlite3
import pandas as pd

conn = sqlite3.connect('medical_tracker.db')
df = pd.read_sql_query('SELECT * FROM case_logs', conn)
print("Row count:", len(df))
print(df.head())
