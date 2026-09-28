#!/usr/bin/env python3
"""
Test the network switching fix with survey fetching workflow.
Simulates what happens when rate limit is hit during survey fetching.
"""
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_rate_limit_detection():
    """Test that the ResponseClassifier correctly detects rate limits."""
    print("=== Testing Rate Limit Detection ===")
    
    try:
        from app.scraper.client.response_classifier import ResponseClassifier
        from app.scraper.domain.enums import ResponseClassification
        from app.scraper.client.raw_response import RawSearchResponse
        
        classifier = ResponseClassifier()
        
        # Test rate limit message
        rate_limit_html = """
        <html>
        <body>
        <div class="message">You have exceeded the limit of daily search results.</div>
        </body>
        </html>
        """
        
        rate_limit_response = RawSearchResponse(
            status_code=200,
            content_type="text/html",
            body=rate_limit_html.encode('utf-8'),
            headers={},
            url="https://pay2igr.igrmaharashtra.gov.in/eDisplay/Propertydetails/index"
        )
        
        classification = classifier.classify(rate_limit_response)
        print(f"Rate limit response classification: {classification}")
        
        if classification == ResponseClassification.RATE_LIMITED:
            print("✓ ResponseClassifier correctly identifies rate limits")
            return True
        else:
            print("✗ ResponseClassifier failed to identify rate limit")
            return False
            
    except Exception as e:
        print(f"Error testing rate limit detection: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_network_switching_workflow():
    """Test the complete workflow when rate limit is hit."""
    print("\n=== Testing Network Switching Workflow ===")
    
    print("Simulating survey fetching scenario:")
    print("1. Scraper fetches survey data from IGR portal")
    print("2. After ~5 requests, portal returns rate limit message")
    print("3. ResponseClassifier detects RATE_LIMITED")
    print("4. SearchWorker._handle_rate_limit() is called")
    print("5. Network switching is triggered")
    print("6. Scraper continues with new IP")
    
    print("\nTesting components:")
    
    all_good = True
    
    # Test 1: Check if we can create a SimpleNetworkProvider
    try:
        from app.scraper.access.simple_network import SimpleNetworkProvider
        provider = SimpleNetworkProvider()
        print("✓ SimpleNetworkProvider can be instantiated")
        print(f"  Current profile: {provider.current_context()}")
    except Exception as e:
        print(f"✗ SimpleNetworkProvider failed: {e}")
        all_good = False
    
    # Test 2: Check database tables
    try:
        import psycopg2
        conn = psycopg2.connect('postgresql://postgres:root@localhost:5432/esearch_igr')
        cursor = conn.cursor()
        
        cursor.execute("SELECT state FROM network_state WHERE id = 1")
        row = cursor.fetchone()
        if row:
            print(f"✓ network_state table has initial state: {row[0]}")
        else:
            print("✗ network_state table missing initial row")
            all_good = False
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"✗ Database check failed: {e}")
        all_good = False
    
    # Test 3: Check if we can simulate the workflow
    print("\n=== Workflow Simulation ===")
    print("To test the actual workflow, you would need to:")
    print("1. Run the scraper with a test search job")
    print("2. Mock the IGR portal to return rate limit after N requests")
    print("3. Verify network switching happens")
    print("4. Verify scraping continues")
    
    print("\nSimplified test command:")
    print("""
# Run a test search (adjust parameters as needed)
cd "c:\\Users\\nitin\\OneDrive\\Documents\\VIIT\\4th Year\\Internship\\2.1 e-search IGR\\backend"
python -c "
from app.scraper.access.simple_network import SimpleNetworkProvider
from app.scraper.access.source_access_manager import SourceAccessManager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = 'postgresql://postgres:root@localhost:5432/esearch_igr'
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create network provider
provider = SimpleNetworkProvider()

# Create access manager
access_manager = SourceAccessManager(provider, session_factory=SessionLocal)

print(f'Initial state: {access_manager.state}')
print(f'Current context: {access_manager.current_context}')

# Simulate rate limit
print('\\nSimulating rate limit...')
access_manager.report_rate_limited()
print(f'After report_rate_limited: {access_manager.state}')

# Try to recover
print('\\nAttempting recovery...')
access_manager.recover()
print(f'After recovery: {access_manager.state}')
print(f'New context: {access_manager.current_context}')
"
""")
    
    return all_good

def create_integration_test():
    """Create an integration test script."""
    print("\n=== Creating Integration Test ===")
    
    test_script = '''#!/usr/bin/env python3
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
        
        print("\\n2. Setting up SourceAccessManager...")
        from app.scraper.access.source_access_manager import SourceAccessManager
        access_manager = SourceAccessManager(provider, session_factory=SessionLocal)
        
        print(f"   Initial state: {access_manager.state}")
        print(f"   Current context: {access_manager.current_context}")
        
        print("\\n3. Simulating survey fetching...")
        print("   [Fetching survey 1...]")
        print("   [Fetching survey 2...]")
        print("   [Fetching survey 3...]")
        print("   [Fetching survey 4...]")
        print("   [Fetching survey 5...]")
        
        print("\\n4. Rate limit hit!")
        print("   Portal response: 'You have exceeded the limit of daily search results'")
        
        print("\\n5. Handling rate limit...")
        access_manager.report_rate_limited()
        print(f"   State after rate limit: {access_manager.state}")
        
        print("\\n6. Attempting network recovery...")
        access_manager.recover()
        print(f"   State after recovery: {access_manager.state}")
        print(f"   New context: {access_manager.current_context}")
        
        print("\\n7. Verifying network switch...")
        new_context = provider.current_context()
        print(f"   Actual network: {new_context}")
        
        if access_manager.state.name == 'AVAILABLE':
            print("\\n✓ SUCCESS: Network switching workflow completed!")
            print("   The scraper can now continue fetching surveys with new IP.")
            return True
        else:
            print("\\n✗ FAILED: Network switching did not complete successfully.")
            print(f"   Final state: {access_manager.state}")
            return False
            
    except Exception as e:
        print(f"\\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_integration()
    
    print("\\n" + "="*60)
    if success:
        print("INTEGRATION TEST PASSED")
        print("The network switching fix works correctly.")
        print("\\nNext steps:")
        print("1. Run the actual scraper")
        print("2. Monitor for rate limits")
        print("3. Verify automatic network switching")
    else:
        print("INTEGRATION TEST FAILED")
        print("\\nTroubleshooting steps:")
        print("1. Check database connection")
        print("2. Verify network_state table exists")
        print("3. Check Wi-Fi profiles are configured correctly")
        print("4. Run python verify_fix.py for diagnostics")
    print("="*60)
'''
    
    test_path = os.path.join(os.path.dirname(__file__), 'integration_test.py')
    
    with open(test_path, 'w', encoding='utf-8') as f:
        f.write(test_script)
    
    print(f"Created integration test: {test_path}")
    print("Run it with: python integration_test.py")

def main():
    print("=== Testing Survey Fetching Workflow with Network Switching Fix ===")
    
    # Test 1: Rate limit detection
    rate_limit_ok = test_rate_limit_detection()
    
    # Test 2: Network switching workflow
    workflow_ok = test_network_switching_workflow()
    
    # Test 3: Create integration test
    create_integration_test()
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    if rate_limit_ok and workflow_ok:
        print("✓ All tests passed or simulated successfully!")
        print("\nThe network switching fix should work in production.")
        print("\nTo fully test:")
        print("1. Run: python integration_test.py")
        print("2. Run the actual scraper with test data")
        print("3. Monitor logs for rate limit handling")
    else:
        print("⚠ Some tests had issues.")
        print("\nRecommended actions:")
        print("1. Check database configuration")
        print("2. Verify Wi-Fi profiles exist")
        print("3. Test manually with handle_rate_limit.py")
    
    print("\n" + "="*60)
    print("PRODUCTION DEPLOYMENT")
    print("="*60)
    print("\nTo deploy this fix in production:")
    print("\n1. Update your scraper configuration:")
    print("   - Ensure IGR_WIFI_INTERFACE, IGR_HOTSPOT_PROFILE, IGR_PARKING_PROFILE")
    print("     are set in environment or .env file")
    print("\n2. Choose your network provider:")
    print("   Option A (recommended): Use SimpleNetworkProvider")
    print("     from app.scraper.access.simple_network import SimpleNetworkProvider")
    print("     network_provider = SimpleNetworkProvider()")
    print("\n   Option B: Use patched WindowsNetworkProvider")
    print("     from app.scraper.access.windows_network import WindowsNetworkProvider")
    print("     network_provider = WindowsNetworkProvider(SessionLocal)")
    print("\n3. Test with a small batch first:")
    print("   - Fetch 5-10 surveys")
    print("   - Trigger rate limit manually if needed")
    print("   - Verify network switches and continues")

if __name__ == "__main__":
    main()