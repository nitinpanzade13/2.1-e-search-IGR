"""
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
