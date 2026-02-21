import sqlite3
import time

connection = sqlite3.connect('posts_database.db')

with open('posts_schema.sql') as f:
    connection.executescript(f.read())

cur = connection.cursor()

cur.execute(
    "INSERT INTO posts (title, content) VALUES (?, ?)",
    ('First Post', 'Content for the first post')
)

time.sleep(1)

cur.execute(
    "INSERT INTO posts (title, content) VALUES (?, ?)",
    ('Second Post', 'Content for the second post')
)

connection.commit()
connection.close()