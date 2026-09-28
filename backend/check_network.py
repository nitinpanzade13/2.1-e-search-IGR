#!/usr/bin/env python3
import os
import sys
import psycopg2

# Read DATABASE_URL from .env
DATABASE_URL = 'postgresql://postgres:root@localhost:5432/esearch_igr'
try:
    with open('.env', 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('DATABASE_URL='):
                DATABASE_URL = line.strip().split('=', 1)[1]
                break
except:
    pass

print(f"Connecting to: {DATABASE_URL}")

# Parse the DATABASE_URL
# postgresql://postgres:root@localhost:5432/esearch_igr
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
        
        # Check network_configs
        print("\n=== Network Configs ===")
        cursor.execute("SELECT id, profile_name, interface_name, priority, role, is_enabled FROM network_configs ORDER BY priority")
        rows = cursor.fetchall()
        for row in rows:
            print(f"Profile: {row[1]}, Interface: {row[2]}, Priority: {row[3]}, Role: {row[4]}, Enabled: {row[5]}")
        
        # Check if network_state exists
        print("\n=== Network State ===")
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'network_state'
            )
        """)
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            cursor.execute("SELECT id, state, current_profile, recovery_attempts, last_recovery_result FROM network_state WHERE id = 1")
            row = cursor.fetchone()
            if row:
                print(f"State: {row[1]}, Current Profile: {row[2]}")
                print(f"Recovery Attempts: {row[3]}, Last Result: {row[4]}")
            else:
                print("No network_state row found")
        else:
            print("network_state table does not exist")
            
        # Check SourceRequestLedger for rate limited entries
        print("\n=== Recent Rate Limited Requests ===")
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'source_request_ledger'
            )
        """)
        ledger_exists = cursor.fetchone()[0]
        
        if ledger_exists:
            cursor.execute("""
                SELECT started_at, rate_limited, response_status 
                FROM source_request_ledger 
                WHERE rate_limited = true 
                ORDER BY started_at DESC 
                LIMIT 5
            """)
            rows = cursor.fetchall()
            if rows:
                for row in rows:
                    print(f"Time: {row[0]}, Rate Limited: {row[1]}, Status: {row[2]}")
            else:
                print("No rate limited requests found")
        else:
            print("source_request_ledger table does not exist")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()