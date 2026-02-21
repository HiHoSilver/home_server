import sqlite3

conn = sqlite3.connect("thermo_database.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT * FROM thermo ORDER BY created DESC LIMIT 5")
rows = cur.fetchall()

for row in rows:
    print(dict(row))

conn.close()
