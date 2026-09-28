#!/usr/bin/env python3
import psycopg2

DATABASE_URL = 'postgresql://postgres:root@localhost:5432/esearch_igr'

# Parse the DATABASE_URL
url_parts = DATABASE_URL.split('://')[1].split('@')
user_pass = url_parts[0].split(':')
host_port_db = url_parts[1].split('/')
host_port = host_port_db[0].split(':')

username = user_pass[0]
password = user_pass[1] if len(user_pass) > 1 else ''
host = host_port[0]
port = host_port[1] if len(host_port) > 1 else '5432'
database = host_port_db[1]

def main():
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Get all tables
        print("=== All Tables ===")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        for table in tables:
            print(f"  - {table[0]}")
        
        # Check alembic_version table
        print("\n=== Alembic Version ===")
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'alembic_version'
            )
        """)
        alembic_exists = cursor.fetchone()[0]
        
        if alembic_exists:
            cursor.execute("SELECT version_num FROM alembic_version")
            version = cursor.fetchone()
            print(f"Current migration version: {version[0] if version else 'None'}")
        else:
            print("alembic_version table does not exist (no migrations applied)")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()