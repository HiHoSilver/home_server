import sqlite3

with sqlite3.connect("thermo_database.db") as connection:
    with open("thermo_schema.sql") as f:
        connection.executescript(f.read())
