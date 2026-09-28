#!/usr/bin/env python3
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

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

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def main():
    db = SessionLocal()
    try:
        # Check network_configs
        print("\n=== Network Configs ===")
        result = db.execute(text("SELECT id, profile_name, interface_name, priority, role, is_enabled FROM network_configs ORDER BY priority"))
        for row in result:
            print(f"Profile: {row.profile_name}, Interface: {row.interface_name}, Priority: {row.priority}, Role: {row.role}, Enabled: {row.is_enabled}")
        
        # Check network_state
        print("\n=== Network State ===")
        try:
            result = db.execute(text("SELECT id, state, current_profile, recovery_attempts, last_recovery_result FROM network_state WHERE id = 1"))
            row = result.fetchone()
            if row:
                print(f"State: {row.state}, Current Profile: {row.current_profile}")
                print(f"Recovery Attempts: {row.recovery_attempts}, Last Result: {row.last_recovery_result}")
            else:
                print("No network_state row found")
        except Exception as e:
            print(f"network_state table doesn't exist or error: {e}")
            
        # Check SourceRequestLedger for rate limited entries
        print("\n=== Recent Rate Limited Requests ===")
        result = db.execute(text("""
            SELECT started_at, rate_limited, response_status 
            FROM source_request_ledger 
            WHERE rate_limited = true 
            ORDER BY started_at DESC 
            LIMIT 5
        """))
        for row in result:
            print(f"Time: {row.started_at}, Rate Limited: {row.rate_limited}, Status: {row.response_status}")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()