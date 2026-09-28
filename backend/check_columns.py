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
        
        # Check network_configs columns
        print("=== network_configs columns ===")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'network_configs' 
            ORDER BY ordinal_position
        """)
        for col in cursor.fetchall():
            print(f"  {col[0]}: {col[1]}")
        
        # Check if network_state table exists
        print("\n=== Checking network_state table ===")
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'network_state'
            )
        """)
        exists = cursor.fetchone()[0]
        print(f"network_state table exists: {exists}")
        
        if exists:
            print("\n=== network_state columns ===")
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'network_state' 
                ORDER BY ordinal_position
            """)
            for col in cursor.fetchall():
                print(f"  {col[0]}: {col[1]}")
        
        # Check if network_configs has role column
        print("\n=== Checking network_configs for 'role' column ===")
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'network_configs' 
                AND column_name = 'role'
            )
        """)
        has_role = cursor.fetchone()[0]
        print(f"network_configs has 'role' column: {has_role}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()