#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.scraper.access.windows_network import WindowsNetworkProvider
from app.scraper.access.source_access_manager import SourceAccessManager

# Setup database connection
DATABASE_URL = 'postgresql://postgres:root@localhost:5432/esearch_igr'
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_network_state_issue():
    print("Testing network state table issue...")
    
    try:
        # Create WindowsNetworkProvider
        network_provider = WindowsNetworkProvider(SessionLocal)
        
        # Create SourceAccessManager - this should fail because network_state table doesn't exist
        print("Creating SourceAccessManager...")
        access_manager = SourceAccessManager(network_provider, session_factory=SessionLocal)
        print("SourceAccessManager created successfully")
        
        # Try to get state
        print(f"Current state: {access_manager.state}")
        print(f"Current context: {access_manager.current_context}")
        
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        
        # Check if it's a table doesn't exist error
        if "network_state" in str(e).lower() or "relation" in str(e).lower():
            print("\n=== ISSUE IDENTIFIED ===")
            print("The 'network_state' table doesn't exist in the database.")
            print("This table is required by SourceAccessManager.")
            print("It should have been created by migration: f10faf674da8_add_networkstate_and_networkconfig_role")
            
            # Check if migration was applied
            print("\n=== CHECKING MIGRATION STATUS ===")
            db = SessionLocal()
            try:
                # Check if network_state table exists
                result = db.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'network_state'
                    )
                """).scalar()
                print(f"network_state table exists: {result}")
                
                # Check alembic version
                result = db.execute("SELECT version_num FROM alembic_version").scalar()
                print(f"Current alembic version: {result}")
            finally:
                db.close()

def test_netswitch():
    print("\n=== Testing netswitch functionality ===")
    
    # Check if we can run netsh commands
    import subprocess
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("netsh command successful")
            # Parse current profile
            for line in result.stdout.splitlines():
                if "Profile" in line and ":" in line:
                    profile = line.split(":", 1)[1].strip()
                    print(f"Current profile: {profile}")
                    break
        else:
            print(f"netsh failed: {result.stderr}")
    except Exception as e:
        print(f"Cannot run netsh: {e}")

if __name__ == "__main__":
    test_network_state_issue()
    test_netswitch()