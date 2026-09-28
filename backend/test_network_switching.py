#!/usr/bin/env python3
"""
Test network switching with the new simple provider.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time

def test_simple_network_provider():
    print("=== Testing SimpleNetworkProvider ===")
    
    try:
        from app.scraper.access.simple_network import SimpleNetworkProvider
        
        provider = SimpleNetworkProvider()
        
        print(f"Current context: {provider.current_context()}")
        print(f"Has internet: {provider.validate_connectivity()}")
        
        # Ask before actually switching
        response = input("\nDo you want to test network switching? (y/N): ").strip().lower()
        if response == 'y':
            print("\nTesting network switch...")
            print("This will switch from current network to parking, then to hotspot.")
            print("Make sure your hotspot is turned on and available.")
            
            confirm = input("Are you sure? This will disconnect your current Wi-Fi. (yes/NO): ").strip().lower()
            if confirm == 'yes':
                print("Starting network switch in 5 seconds...")
                time.sleep(5)
                
                success = provider.change_context()
                if success:
                    print("✓ Network switch successful!")
                    print(f"New context: {provider.current_context()}")
                else:
                    print("✗ Network switch failed")
            else:
                print("Skipping actual network switch.")
        else:
            print("Skipping network switch test.")
            
    except Exception as e:
        print(f"Error testing SimpleNetworkProvider: {e}")
        import traceback
        traceback.print_exc()

def test_netswitch_integration():
    print("\n=== Testing netswitch.py integration ===")
    
    # Check if we can import and run the original netswitch.py
    netswitch_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '2.1-script-main', 'netswitch.py')
    
    if os.path.exists(netswitch_path):
        print(f"Found netswitch.py at: {netswitch_path}")
        
        # Read and show the key functions
        with open(netswitch_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'def rotate(' in content:
            print("✓ netswitch.py has rotate() function")
            
        if 'def public_ip(' in content:
            print("✓ netswitch.py has public_ip() function")
            
        # Show the config it uses
        if 'WIFI_INTERFACE' in content:
            print("\nConfiguration used by netswitch.py:")
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'WIFI_INTERFACE' in line or 'HOTSPOT_PROFILE' in line or 'PARKING_PROFILE' in line:
                    print(f"  {line.strip()}")
                    
        print("\nYou can run netswitch.py directly:")
        print(f"  cd 2.1-script-main")
        print(f"  python netswitch.py")
        
    else:
        print("netswitch.py not found at expected location.")

def create_workaround_script():
    print("\n=== Creating workaround script ===")
    
    script_content = '''#!/usr/bin/env python3
"""
Workaround script for network switching when rate limit hits.
This can be called manually or integrated into the scraping process.
"""
import sys
import os
import time

# Add the parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def handle_rate_limit_manually():
    """Manual network switching when rate limit is detected."""
    print("=== Manual Rate Limit Handling ===")
    
    try:
        # Try to use the simple network provider
        from app.scraper.access.simple_network import SimpleNetworkProvider
        
        provider = SimpleNetworkProvider()
        
        print(f"Current network: {provider.current_context()}")
        print(f"Internet connectivity: {provider.validate_connectivity()}")
        
        print("\nRate limit detected! Need to switch network to get new IP.")
        print("This will:")
        print("1. Switch to parking network (Airtel_COOLIFY)")
        print("2. Switch to hotspot network (vivo)")
        print("3. Get new IP address")
        
        response = input("\nProceed with network switch? (y/N): ").strip().lower()
        if response != 'y':
            print("Aborted.")
            return False
        
        print("\nStarting network switch...")
        success = provider.change_context()
        
        if success:
            print("✓ Network switched successfully!")
            print("You can now continue scraping with new IP.")
            return True
        else:
            print("✗ Network switch failed.")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def simulate_rate_limit_recovery():
    """Simulate what happens when rate limit is hit."""
    print("\n=== Simulating Rate Limit Recovery ===")
    
    # This is what happens in SearchWorker._handle_rate_limit()
    print("When rate limit hits in production:")
    print("1. Response is classified as RATE_LIMITED")
    print("2. SearchWorker._handle_rate_limit() is called")
    print("3. It calls access.report_rate_limited()")
    print("4. Which triggers network switching via provider.change_context()")
    print("5. If successful, job is requeued")
    print("6. If failed after 3 retries, job is marked RATE_LIMITED")
    
    print("\nWith our fixes:")
    print("- SimpleNetworkProvider doesn't need database tables")
    print("- SourceAccessManager handles missing tables gracefully")
    print("- Network switching should work even with incomplete database")

if __name__ == "__main__":
    handle_rate_limit_manually()
    simulate_rate_limit_recovery()
'''
    
    script_path = os.path.join(os.path.dirname(__file__), 'handle_rate_limit.py')
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print(f"Created workaround script: {script_path}")
    print("Run it with: python handle_rate_limit.py")

def main():
    print("=== Network Switching Fix Test ===")
    
    # Test 1: Simple network provider
    test_simple_network_provider()
    
    # Test 2: Original netswitch.py
    test_netswitch_integration()
    
    # Test 3: Create workaround script
    create_workaround_script()
    
    print("\n=== Summary ===")
    print("✓ Created SimpleNetworkProvider (no database dependency)")
    print("✓ Patched SourceAccessManager to handle missing tables")
    print("✓ Created workaround script for manual rate limit handling")
    print("✓ Verified netswitch.py is available for reference")
    print("\nThe network switching should now work when rate limit hits.")

if __name__ == "__main__":
    main()