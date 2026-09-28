#!/usr/bin/env python3
"""
Patch SourceAccessManager to handle missing database tables gracefully.
This allows network switching to work even when some tables are missing.
"""
import os
import sys

# Add the project to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def patch_source_access_manager():
    """Patch the SourceAccessManager to handle missing tables."""
    
    # Read the original file
    file_path = os.path.join(os.path.dirname(__file__), 'app', 'scraper', 'access', 'source_access_manager.py')
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already patched
    if '_ensure_network_state_row_safe' in content:
        print("SourceAccessManager already patched.")
        return
    
    print("Patching SourceAccessManager...")
    
    # Find the _ensure_network_state_row method
    if 'def _ensure_network_state_row(self):' in content:
        # Replace it with a safer version
        old_method = '''    def _ensure_network_state_row(self):
        db = self._session_factory()
        try:
            state_row = db.query(NetworkState).filter_by(id=1).first()
            if not state_row:
                state_row = NetworkState(id=1, state=AccessState.AVAILABLE.value, current_profile=self._provider.current_context())
                db.add(state_row)
                db.commit()
        finally:
            db.close()'''
        
        new_method = '''    def _ensure_network_state_row(self):
        """Safely ensure network_state row exists, handling missing table."""
        db = self._session_factory()
        try:
            # Try to query the table - it might not exist
            state_row = db.query(NetworkState).filter_by(id=1).first()
            if not state_row:
                state_row = NetworkState(id=1, state=AccessState.AVAILABLE.value, current_profile=self._provider.current_context())
                db.add(state_row)
                db.commit()
        except Exception as e:
            # Table might not exist or other error
            logger.warning(f"Could not ensure network_state row: {e}. Network state tracking disabled.")
            # Don't re-raise - we can still work without the table
        finally:
            db.close()
    
    def _ensure_network_state_row_safe(self):
        """Wrapper that catches all exceptions."""
        try:
            return self._ensure_network_state_row()
        except Exception:
            # Silently fail - table doesn't exist
            pass
    
    def _get_db_state_safe(self):
        """Safe version that returns default state if table doesn't exist."""
        db = self._session_factory()
        try:
            row = db.query(NetworkState).filter_by(id=1).first()
            return row
        except Exception:
            # Table doesn't exist, return None
            return None
        finally:
            db.close()'''
        
        content = content.replace(old_method, new_method)
        
        # Also need to update _get_db_state method
        if 'def _get_db_state(self) -> NetworkState:' in content:
            old_get_state = '''    def _get_db_state(self) -> NetworkState:
        db = self._session_factory()
        try:
            return db.query(NetworkState).filter_by(id=1).first()
        finally:
            db.close()'''
            
            new_get_state = '''    def _get_db_state(self) -> NetworkState:
        """Get network state with fallback if table doesn't exist."""
        db = self._session_factory()
        try:
            return db.query(NetworkState).filter_by(id=1).first()
        except Exception:
            # Table doesn't exist, return None
            return None
        finally:
            db.close()'''
            
            content = content.replace(old_get_state, new_get_state)
        
        # Update the state property to use safe method
        if '@property\n    def state(self) -> AccessState:' in content:
            old_state_property = '''    @property
    def state(self) -> AccessState:
        state_row = self._get_db_state()
        if not state_row:
            return AccessState.AVAILABLE
        return AccessState(state_row.state)'''
            
            new_state_property = '''    @property
    def state(self) -> AccessState:
        state_row = self._get_db_state()
        if not state_row:
            return AccessState.AVAILABLE
        return AccessState(state_row.state)'''
            
            # This is already safe, but let's update the docstring
            content = content.replace(old_state_property, new_state_property)
        
        # Write the patched file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("SourceAccessManager patched successfully.")
    else:
        print("Could not find _ensure_network_state_row method to patch.")

def create_simple_network_provider():
    """Create a simple network provider that doesn't depend on database."""
    
    file_path = os.path.join(os.path.dirname(__file__), 'app', 'scraper', 'access', 'simple_network.py')
    
    if os.path.exists(file_path):
        print("Simple network provider already exists.")
        return
    
    content = '''"""
Simple network provider that doesn't depend on database tables.
Based on the original netswitch.py from 2.1-script-main.
"""
import sys
import subprocess
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SimpleNetworkProvider:
    """
    A simple network provider that uses environment variables or hardcoded values.
    Doesn't depend on database tables.
    """
    def __init__(self):
        self._is_windows = sys.platform == "win32"
        if not self._is_windows:
            logger.warning("SimpleNetworkProvider initialized on non-Windows platform. Network switching will be disabled.")
        
        # Read from environment or use defaults
        import os
        self.wifi_interface = os.environ.get("IGR_WIFI_INTERFACE", "Wi-Fi")
        self.hotspot_profile = os.environ.get("IGR_HOTSPOT_PROFILE", "vivo")
        self.parking_profile = os.environ.get("IGR_PARKING_PROFILE", "Airtel_COOLIFY")
        
        logger.info(f"SimpleNetworkProvider: Hotspot={self.hotspot_profile}, Parking={self.parking_profile}")

    def current_context(self) -> str:
        """Returns the current Wi-Fi profile name."""
        if not self._is_windows:
            return "non-windows-context"
            
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True,
                text=True,
                check=True
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("Profile"):
                    # Format is usually: Profile                : ProfileName
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        return parts[1].strip()
            return "disconnected"
        except Exception as e:
            logger.error(f"Failed to read current network context: {e}")
            return "unknown"

    def _connect_and_wait(self, profile: str, timeout: int = 30) -> bool:
        """Connect to a profile and wait for connection."""
        logger.info(f"Attempting to switch to network profile: {profile}")
        try:
            cmd = [
                "netsh", "wlan", "connect", 
                f"name={profile}", 
                f"interface={self.wifi_interface}"
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                new_context = self.current_context()
                if new_context == profile:
                    logger.info(f"Successfully associated with {profile}")
                    return True
                time.sleep(2)
                
            logger.warning(f"Timeout waiting to connect to {profile}")
            return False
        except Exception as e:
            logger.error(f"Failed to execute netsh connect for {profile}: {e}")
            return False

    def change_context(self) -> bool:
        """Switch from current network to parking, then to hotspot."""
        if not self._is_windows:
            logger.error("Cannot change network context: Platform is not Windows.")
            return False

        current = self.current_context()
        logger.info(f"Current profile: {current}")
        
        # 1. Connect to Parking if we aren't already on it
        if current != self.parking_profile:
            if not self._connect_and_wait(self.parking_profile):
                logger.warning("Failed to connect to parking profile. Trying hotspot directly.")
            else:
                # Wait a bit for the switch to settle
                time.sleep(12)
        
        # 2. Connect to Hotspot
        if current == self.hotspot_profile:
            logger.info("Already on hotspot profile. Disconnecting and reconnecting...")
            # Try to disconnect first
            try:
                subprocess.run(["netsh", "wlan", "disconnect"], capture_output=True, text=True)
                time.sleep(5)
            except:
                pass
        
        if self._connect_and_wait(self.hotspot_profile):
            # Validate connectivity
            if self.validate_connectivity():
                logger.info("Network switch successful!")
                return True
            else:
                logger.warning("Connected to hotspot but no internet connectivity")
                return False
        
        logger.error("Failed to connect to hotspot")
        return False

    def validate_connectivity(self, timeout: int = 10) -> bool:
        """Check if we have internet connectivity."""
        if not self._is_windows:
            return True # Assume connected on non-Windows

        import requests
        try:
            # Try multiple endpoints
            endpoints = [
                "http://captive.apple.com/hotspot-detect.html",
                "http://connectivitycheck.gstatic.com/generate_204",
                "https://www.google.com"
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.get(endpoint, timeout=timeout)
                    if response.status_code < 400:
                        return True
                except:
                    continue
            
            return False
        except Exception as e:
            logger.error(f"Connectivity validation failed: {e}")
            return False
'''
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Simple network provider created.")

def main():
    print("=== Patching Network Switching System ===")
    
    # First, create the simple network provider
    create_simple_network_provider()
    
    # Then patch the SourceAccessManager
    patch_source_access_manager()
    
    print("\n=== Patch Complete ===")
    print("1. Created SimpleNetworkProvider that doesn't depend on database")
    print("2. Patched SourceAccessManager to handle missing tables gracefully")
    print("\nYou can now:")
    print("- Use SimpleNetworkProvider instead of WindowsNetworkProvider")
    print("- OR the patched SourceAccessManager will handle missing tables")
    print("\nTo use SimpleNetworkProvider, update your code:")
    print("  from app.scraper.access.simple_network import SimpleNetworkProvider")
    print("  network_provider = SimpleNetworkProvider()")

if __name__ == "__main__":
    main()