import sqlite3
import os

os.remove('mta.db')

conn = sqlite3.connect('mta.db')
c = conn.cursor()
c.execute('''CREATE TABLE users
             (date_created text, date_updated text, id text, station integer, direction text)''')
conn.commit()
conn.close()
