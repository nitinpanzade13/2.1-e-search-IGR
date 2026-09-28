#!/usr/bin/env python3
import psycopg2
import subprocess

def check_database_issue():
    print("=== Checking Database Issue ===")
    
    DATABASE_URL = 'postgresql://postgres:root@localhost:5432/esearch_igr'
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # 1. Check if network_state table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'network_state'
            )
        """)
        network_state_exists = cursor.fetchone()[0]
        print(f"1. network_state table exists: {network_state_exists}")
        
        if not network_state_exists:
            print("   ❌ PROBLEM: network_state table is missing!")
            print("   This table is required by SourceAccessManager")
            
            # Check what migration should have created it
            cursor.execute("SELECT version_num FROM alembic_version")
            current_version = cursor.fetchone()[0]
            print(f"   Current alembic version: {current_version}")
            
            # Check migration history
            print("\n   Checking migration f10faf674da8...")
            cursor.execute("""
                SELECT version_num, description 
                FROM alembic_version 
                CROSS JOIN (VALUES ('f10faf674da8', 'Add NetworkState and NetworkConfig role')) as expected(exp_version, exp_desc)
                WHERE version_num = exp_version
            """)
            migration_applied = cursor.fetchone()
            if migration_applied:
                print(f"   ✓ Migration {migration_applied[0]} applied: {migration_applied[1]}")
                print("   But table is still missing - migration may have failed or been rolled back")
            else:
                print("   ✗ Migration f10faf674da8 not found in alembic_version")
        
        # 2. Check network_configs table
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'network_configs'
            )
        """)
        network_configs_exists = cursor.fetchone()[0]
        print(f"\n2. network_configs table exists: {network_configs_exists}")
        
        if network_configs_exists:
            cursor.execute("SELECT COUNT(*) FROM network_configs")
            count = cursor.fetchone()[0]
            print(f"   Number of network configs: {count}")
            
            cursor.execute("SELECT profile_name, role, priority, is_enabled FROM network_configs ORDER BY priority")
            configs = cursor.fetchall()
            for config in configs:
                print(f"   - Profile: {config[0]}, Role: {config[1]}, Priority: {config[2]}, Enabled: {config[3]}")
        
        # 3. Check if any other required tables are missing
        required_tables = ['source_request_ledger', 'search_jobs', 'bulk_fetch_jobs']
        print("\n3. Checking other required tables:")
        for table in required_tables:
            cursor.execute(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table}'
                )
            """)
            exists = cursor.fetchone()[0]
            print(f"   {table}: {'✓' if exists else '✗'}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Database error: {e}")

def check_netswitch_capability():
    print("\n=== Checking Network Switching Capability ===")
    
    try:
        # Test if netsh is available
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✓ netsh command works")
            
            # Parse current profile
            current_profile = None
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("Profile") and ":" in line:
                    current_profile = line.split(":", 1)[1].strip()
                    break
            
            if current_profile:
                print(f"  Current Wi-Fi profile: {current_profile}")
            else:
                print("  Could not determine current profile")
                
            # Check if we have the profiles from database
            print("\n  Checking if we can connect to profiles...")
            profiles_to_test = ["Airtel_COOLIFY", "vivo"]
            for profile in profiles_to_test:
                print(f"  Testing connection to '{profile}'...")
                test_result = subprocess.run(
                    ["netsh", "wlan", "connect", f"name={profile}"],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                if test_result.returncode == 0:
                    print(f"    ✓ Can connect to {profile}")
                else:
                    print(f"    ✗ Cannot connect to {profile}: {test_result.stderr[:100]}...")
                    
        else:
            print(f"✗ netsh failed: {result.stderr[:200]}")
            
    except FileNotFoundError:
        print("✗ netsh command not found (not Windows or netsh not in PATH)")
    except Exception as e:
        print(f"✗ Error testing netsh: {e}")

def simulate_rate_limit_scenario():
    print("\n=== Simulating Rate Limit Scenario ===")
    
    print("When rate limit hits:")
    print("1. ResponseClassifier detects 'you have exceeded the limit of daily search results'")
    print("2. Returns RATE_LIMITED classification")
    print("3. SearchWorker._handle_rate_limit() is called")
    print("4. Calls access.report_rate_limited()")
    print("5. Which calls access.recover()")
    print("6. SourceAccessManager tries to query network_state table")
    print("7. ❌ FAILS because network_state table doesn't exist")
    print("8. Network switching never happens")
    print("9. Job gets marked as RATE_LIMITED without retry")
    
    print("\nThe fix should:")
    print("1. Create the missing network_state table")
    print("2. OR make SourceAccessManager handle missing table gracefully")
    print("3. Ensure WindowsNetworkProvider can actually switch networks")

if __name__ == "__main__":
    check_database_issue()
    check_netswitch_capability()
    simulate_rate_limit_scenario()