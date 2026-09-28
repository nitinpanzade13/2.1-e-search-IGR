#!/usr/bin/env python3
import psycopg2

DATABASE_URL = 'postgresql://postgres:root@localhost:5432/esearch_igr'

def main():
    print("Creating missing network_state table...")
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'network_state'
            )
        """)
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            print("network_state table already exists. Checking structure...")
            
            # Check if we have the right columns
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'network_state' 
                ORDER BY ordinal_position
            """)
            columns = cursor.fetchall()
            print(f"Table has {len(columns)} columns:")
            for col in columns:
                print(f"  {col[0]}: {col[1]}")
                
            # Check if we have row with id=1
            cursor.execute("SELECT id, state, current_profile FROM network_state WHERE id = 1")
            row = cursor.fetchone()
            if row:
                print(f"\nExisting row: id={row[0]}, state={row[1]}, profile={row[2]}")
            else:
                print("\nNo row with id=1 found, inserting...")
                cursor.execute("""
                    INSERT INTO network_state (id, state, current_profile, recovery_attempts)
                    VALUES (1, 'AVAILABLE', 'Airtel_COOLIFY', 0)
                """)
                print("Inserted initial row")
        else:
            print("Creating network_state table...")
            
            # Create the table
            cursor.execute("""
                CREATE TABLE network_state (
                    id INTEGER PRIMARY KEY,
                    state VARCHAR NOT NULL,
                    current_profile VARCHAR,
                    recovery_started_at TIMESTAMP,
                    recovery_owner VARCHAR,
                    last_recovery_start TIMESTAMP,
                    last_recovery_end TIMESTAMP,
                    last_recovery_result VARCHAR,
                    recovery_attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create sequence
            cursor.execute("""
                CREATE SEQUENCE network_state_id_seq
                    START WITH 1
                    INCREMENT BY 1
                    NO MINVALUE
                    NO MAXVALUE
                    CACHE 1
            """)
            
            # Set default value
            cursor.execute("""
                ALTER TABLE network_state 
                ALTER COLUMN id SET DEFAULT nextval('network_state_id_seq')
            """)
            
            # Insert initial row
            cursor.execute("""
                INSERT INTO network_state (id, state, current_profile, recovery_attempts)
                VALUES (1, 'AVAILABLE', 'Airtel_COOLIFY', 0)
            """)
            
            # Create index
            cursor.execute("CREATE INDEX idx_network_state_id ON network_state(id)")
            
            print("network_state table created successfully!")
        
        # Verify other required tables
        print("\n=== Verifying other required tables ===")
        required_tables = ['source_request_ledger', 'search_jobs', 'bulk_fetch_jobs']
        for table in required_tables:
            cursor.execute(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table}'
                )
            """)
            exists = cursor.fetchone()[0]
            print(f"{table}: {'✓' if exists else '✗'}")
            
            if not exists and table == 'source_request_ledger':
                print(f"  WARNING: {table} table is missing. This table tracks rate limited requests.")
        
        cursor.close()
        conn.close()
        
        print("\n=== Database fix complete ===")
        print("The network_state table has been created/verified.")
        print("SourceAccessManager should now work correctly.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()