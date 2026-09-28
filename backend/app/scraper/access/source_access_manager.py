import threading
from enum import Enum
import time
import socket
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.scraper.access.network_provider import NetworkProvider
from app.scraper.domain.exceptions import SourceAccessUnavailable
from app.models.system import NetworkState
import logging

logger = logging.getLogger(__name__)

class AccessState(Enum):
    AVAILABLE = "AVAILABLE"
    EXHAUSTED = "EXHAUSTED"
    NETWORK_ERROR = "NETWORK_ERROR"
    NETWORK_CHANGE_REQUIRED = "NETWORK_CHANGE_REQUIRED"
    RECOVERING = "RECOVERING"
    UNAVAILABLE = "UNAVAILABLE"

class SourceAccessManager:
    """
    Manages admission, rate-limit state, and recovery orchestration for the source scraper.
    Coordinates across separate OS processes via a PostgreSQL shared `network_state` row
    and an advisory lock (mutex).
    """
    ADVISORY_LOCK_ID = 88889999
    RECOVERY_STALE_TIMEOUT_SEC = 120

    def __init__(self, network_provider: NetworkProvider, session_factory: sessionmaker):
        self._provider = network_provider
        self._session_factory = session_factory
        self._local_lock = threading.RLock()
        self._process_id = f"{socket.gethostname()}-{id(self)}"
        self._ensure_network_state_row()

    def _ensure_network_state_row(self):
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
            db.close()

    def _get_db_state(self) -> NetworkState:
        """Get network state with fallback if table doesn't exist."""
        db = self._session_factory()
        try:
            return db.query(NetworkState).filter_by(id=1).first()
        except Exception:
            # Table doesn't exist, return None
            return None
        finally:
            db.close()

    @property
    def current_context(self) -> str:
        state_row = self._get_db_state()
        return state_row.current_profile if state_row else "unknown"

    @property
    def previous_context(self) -> str | None:
        return None  # Replaced by detailed DB fields if needed

    @property
    def state(self) -> AccessState:
        state_row = self._get_db_state()
        if not state_row:
            return AccessState.AVAILABLE
        return AccessState(state_row.state)

    def acquire(self) -> None:
        """
        Requests admission to perform a source request.
        Raises SourceAccessUnavailable if the state is anything other than AVAILABLE.
        """
        state_row = self._get_db_state()
        if not state_row or AccessState(state_row.state) != AccessState.AVAILABLE:
            raise SourceAccessUnavailable(f"Source access is currently {state_row.state if state_row else 'UNKNOWN'}")

    def report_rate_limited(self) -> None:
        """
        Informs the manager that a source response was classified as RATE_LIMITED.
        Delegates to report_network_error to orchestrate a physical network switch to rotate IPs.
        """
        self.report_network_error()

    def report_network_error(self) -> None:
        """
        Informs the manager that a legitimate network/connectivity error occurred.
        Transitions to NETWORK_ERROR, which permits failover recovery.
        """
        db = self._session_factory()
        try:
            row = db.query(NetworkState).filter_by(id=1).first()
            if row and AccessState(row.state) == AccessState.AVAILABLE:
                row.state = AccessState.NETWORK_ERROR.value
                db.commit()
        finally:
            db.close()

    def recover(self) -> None:
        """
        Attempts to recover from a NETWORK_ERROR or UNAVAILABLE state by orchestrating a 
        network context change via the NetworkProvider, using an advisory lock for cross-process concurrency.
        """
        db = self._session_factory()
        try:
            # 1. Check if we need to recover
            row = db.query(NetworkState).filter_by(id=1).first()
            if not row or AccessState(row.state) in (AccessState.AVAILABLE, AccessState.EXHAUSTED):
                return
            
            # Check for stale recovery
            if AccessState(row.state) == AccessState.RECOVERING:
                if row.recovery_started_at:
                    elapsed = (datetime.utcnow() - row.recovery_started_at).total_seconds()
                    if elapsed < self.RECOVERY_STALE_TIMEOUT_SEC:
                        logger.info(f"Another process ({row.recovery_owner}) is currently recovering. Waiting...")
                        return # Another active process is recovering
        finally:
            db.close()

        # 2. Try to acquire the advisory lock using a raw connection to ensure it is held continuously
        engine = self._session_factory.kw['bind']
        conn = engine.connect()
        try:
            result = conn.execute(text(f"SELECT pg_try_advisory_lock({self.ADVISORY_LOCK_ID})")).scalar()
            if not result:
                logger.info("Failed to acquire advisory lock. Another process is actively handling recovery.")
                return

            # We hold the lock!
            try:
                db = self._session_factory()
                try:
                    # Refresh state to ensure another process didn't just fix it before we got the lock
                    row = db.query(NetworkState).filter_by(id=1).first()
                    if AccessState(row.state) in (AccessState.AVAILABLE, AccessState.EXHAUSTED):
                        return
                    
                    # Mark as RECOVERING
                    row.state = AccessState.RECOVERING.value
                    row.recovery_started_at = datetime.utcnow()
                    row.last_recovery_start = row.recovery_started_at
                    row.recovery_owner = self._process_id
                    row.recovery_attempts += 1
                    db.commit()
                finally:
                    db.close()

                # Perform the physical recovery
                logger.info(f"Process {self._process_id} initiating physical network recovery...")
                success = self._provider.change_context()
                
                db = self._session_factory()
                try:
                    # Re-fetch row inside the lock to update results
                    row = db.query(NetworkState).filter_by(id=1).first()
                    row.last_recovery_end = datetime.utcnow()
                    row.recovery_started_at = None
                    row.recovery_owner = None
                    row.current_profile = self._provider.current_context()
                    
                    if success:
                        row.state = AccessState.AVAILABLE.value
                        row.last_recovery_result = "SUCCESS"
                        logger.info("Network recovery successful.")
                    else:
                        row.state = AccessState.UNAVAILABLE.value
                        row.last_recovery_result = "FAILURE"
                        logger.error("Network recovery failed.")
                    
                    db.commit()
                finally:
                    db.close()
            finally:
                conn.execute(text(f"SELECT pg_advisory_unlock({self.ADVISORY_LOCK_ID})"))
                conn.commit()
        finally:
            conn.close()
