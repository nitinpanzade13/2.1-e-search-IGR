import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, user='postgres', password='root', dbname='esearch_igr')
cur = conn.cursor()
cur.execute("SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' AND indexname NOT LIKE '%_pkey'")
for row in cur.fetchall():
    print(f"Table: {row[0]}, Index: {row[1]}, Def: {row[2]}")
