import sys
import subprocess
import time
import logging
from typing import Optional
from sqlalchemy.orm import sessionmaker

from app.scraper.access.network_provider import NetworkProvider
from app.models.system import NetworkConfig

logger = logging.getLogger(__name__)

class WindowsNetworkProvider(NetworkProvider):
    """
    A Windows-specific NetworkProvider that uses `netsh wlan` to switch Wi-Fi profiles
    based on the configurations defined by the Administrator in the database.
    """
    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory
        self._is_windows = sys.platform == "win32"
        if not self._is_windows:
            logger.warning("WindowsNetworkProvider initialized on non-Windows platform. Network switching will be disabled.")

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

    def _connect_and_wait(self, config: NetworkConfig) -> bool:
        logger.info(f"Attempting to switch to network profile: {config.profile_name} on interface {config.interface_name}")
        try:
            cmd = [
                "netsh", "wlan", "connect", 
                f"name={config.profile_name}", 
                f"interface={config.interface_name}"
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            timeout = config.connection_timeout
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                new_context = self.current_context()
                if new_context == config.profile_name:
                    logger.info(f"Successfully associated with {config.profile_name}")
                    return True
                time.sleep(2)
                
            logger.warning(f"Timeout waiting to connect to {config.profile_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to execute netsh connect for {config.profile_name}: {e}")
            return False

    def change_context(self) -> bool:
        if not self._is_windows:
            logger.error("Cannot change network context: Platform is not Windows.")
            return False

        current = self.current_context()
        
        db = self._session_factory()
        try:
            configs = db.query(NetworkConfig).filter(
                NetworkConfig.is_enabled == True
            ).order_by(NetworkConfig.priority).all()
            
            if not configs:
                logger.warning("No enabled network configurations found in database.")
                return False

            parking_configs = [c for c in configs if c.role == "PARKING"]
            failover_configs = [c for c in configs if c.role == "FAILOVER"]
            
            # 1. Connect to Parking if we aren't already on one
            if current not in [c.profile_name for c in parking_configs]:
                for p_config in parking_configs:
                    if self._connect_and_wait(p_config):
                        break
                else:
                    logger.warning("Failed to connect to any PARKING profile. Proceeding to FAILOVER directly.")

            # 2. Connect to Failover
            for f_config in failover_configs:
                if f_config.profile_name == current:
                    continue # Try to rotate to a new one if possible

                if self._connect_and_wait(f_config):
                    # Validate connectivity
                    if self.validate_connectivity(timeout=f_config.validation_timeout):
                        return True
                    else:
                        logger.warning(f"Connectivity validation failed for {f_config.profile_name}. Trying next.")
                        
            logger.error("Exhausted all FAILOVER configurations without successful internet connection.")
            return False
        finally:
            db.close()

    def validate_connectivity(self, timeout: int = 10) -> bool:
        if not self._is_windows:
            return True # Assume connected on non-Windows

        import requests
        try:
            response = requests.get("http://captive.apple.com/hotspot-detect.html", timeout=timeout)
            return response.status_code == 200 and "Success" in response.text
        except Exception as e:
            logger.error(f"Connectivity validation failed: {e}")
            return False
