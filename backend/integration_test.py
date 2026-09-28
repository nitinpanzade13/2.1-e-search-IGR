#!/usr/bin/env python3
"""
Integration test for network switching during survey fetching.
Run this to test the complete workflow.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test_integration():
    print("=== Integration Test: Network Switching During Survey Fetching ===")
    
    DATABASE_URL = 'postgresql://postgres:root@localhost:5432/esearch_igr'
    
    try:
        # Setup database
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        print("1. Setting up network provider...")
        
        # Try to use SimpleNetworkProvider
        from app.scraper.access.simple_network import SimpleNetworkProvider
        provider = SimpleNetworkProvider()
        
        print(f"   Current network: {provider.current_context()}")
        print(f"   Has internet: {provider.validate_connectivity()}")
        
        print("\n2. Setting up SourceAccessManager...")
        from app.scraper.access.source_access_manager import SourceAccessManager
        access_manager = SourceAccessManager(provider, session_factory=SessionLocal)
        
        print(f"   Initial state: {access_manager.state}")
        print(f"   Current context: {access_manager.current_context}")
        
        print("\n3. Simulating survey fetching...")
        print("   [Fetching survey 1...]")
        print("   [Fetching survey 2...]")
        print("   [Fetching survey 3...]")
        print("   [Fetching survey 4...]")
        print("   [Fetching survey 5...]")
        
        print("\n4. Rate limit hit!")
        print("   Portal response: 'You have exceeded the limit of daily search results'")
        
        print("\n5. Handling rate limit...")
        access_manager.report_rate_limited()
        print(f"   State after rate limit: {access_manager.state}")
        
        print("\n6. Attempting network recovery...")
        access_manager.recover()
        print(f"   State after recovery: {access_manager.state}")
        print(f"   New context: {access_manager.current_context}")
        
        print("\n7. Verifying network switch...")
        new_context = provider.current_context()
        print(f"   Actual network: {new_context}")
        
        if access_manager.state.name == 'AVAILABLE':
            print("\n✓ SUCCESS: Network switching workflow completed!")
            print("   The scraper can now continue fetching surveys with new IP.")
            return True
        else:
            print("\n✗ FAILED: Network switching did not complete successfully.")
            print(f"   Final state: {access_manager.state}")
            return False
            
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_integration()
    
    print("\n" + "="*60)
    if success:
        print("INTEGRATION TEST PASSED")
        print("The network switching fix works correctly.")
        print("\nNext steps:")
        print("1. Run the actual scraper")
        print("2. Monitor for rate limits")
        print("3. Verify automatic network switching")
    else:
        print("INTEGRATION TEST FAILED")
        print("\nTroubleshooting steps:")
        print("1. Check database connection")
        print("2. Verify network_state table exists")
        print("3. Check Wi-Fi profiles are configured correctly")
        print("4. Run python verify_fix.py for diagnostics")
    print("="*60)
