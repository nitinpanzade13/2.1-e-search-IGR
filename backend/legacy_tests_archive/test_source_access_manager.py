import pytest
from app.scraper.access.network_provider import NoopNetworkProvider, MockNetworkProvider
from app.scraper.access.source_access_manager import SourceAccessManager, AccessState
from app.scraper.domain.exceptions import SourceAccessUnavailable
from tests.conftest import TestingSessionLocal
from app.models.system import NetworkState

@pytest.fixture
def clean_db():
    db = TestingSessionLocal()
    db.query(NetworkState).delete()
    db.commit()
    db.close()
    yield
    db = TestingSessionLocal()
    db.query(NetworkState).delete()
    db.commit()
    db.close()

def test_initial_state_available(clean_db):
    provider = MockNetworkProvider()
    manager = SourceAccessManager(provider, session_factory=TestingSessionLocal)
    assert manager.state == AccessState.AVAILABLE
    
    # Should permit acquisition
    manager.acquire()

def test_acquire_denied_when_not_available(clean_db):
    provider = MockNetworkProvider()
    manager = SourceAccessManager(provider, session_factory=TestingSessionLocal)
    
    manager.report_network_error()
    assert manager.state == AccessState.NETWORK_ERROR
    
    with pytest.raises(SourceAccessUnavailable):
        manager.acquire()

def test_report_rate_limited_transitions_to_network_error(clean_db):
    manager = SourceAccessManager(MockNetworkProvider(), session_factory=TestingSessionLocal)
    manager.report_rate_limited()
    assert manager.state == AccessState.NETWORK_ERROR
    
    # Reporting rate limit again should keep it network error
    manager.report_rate_limited()
    assert manager.state == AccessState.NETWORK_ERROR

def test_repeated_acquire_network_error_does_not_invoke_network_provider(clean_db):
    provider = MockNetworkProvider()
    manager = SourceAccessManager(provider, session_factory=TestingSessionLocal)
    
    manager.report_network_error()
    
    for _ in range(5):
        with pytest.raises(SourceAccessUnavailable):
            manager.acquire()
            
    assert provider.change_count == 0

def test_recovery_successful_orchestration(clean_db):
    provider = MockNetworkProvider(start_context="A")
    manager = SourceAccessManager(provider, session_factory=TestingSessionLocal)
    
    manager.report_network_error()
    assert manager.state == AccessState.NETWORK_ERROR
    
    # Recover should trigger change_context -> RECOVERING -> validate_connectivity -> AVAILABLE
    manager.recover()
    
    assert provider.change_count == 1
    assert provider.current_context() == "mock_context_2"
    assert manager.state == AccessState.AVAILABLE
    manager.acquire() # Should succeed again

def test_rate_limited_triggers_recover(clean_db):
    provider = MockNetworkProvider(start_context="A")
    manager = SourceAccessManager(provider, session_factory=TestingSessionLocal)
    
    manager.report_rate_limited()
    assert manager.state == AccessState.NETWORK_ERROR
    
    manager.recover()
    assert provider.change_count == 1
    assert manager.state == AccessState.AVAILABLE

def test_recovery_fails_on_change_context(clean_db):
    provider = MockNetworkProvider()
    provider.will_fail_change = True
    manager = SourceAccessManager(provider, session_factory=TestingSessionLocal)
    
    manager.report_network_error()
    manager.recover()
    
    assert manager.state == AccessState.UNAVAILABLE
    with pytest.raises(SourceAccessUnavailable):
        manager.acquire()

def test_recovery_on_available_state_is_ignored(clean_db):
    provider = MockNetworkProvider()
    manager = SourceAccessManager(provider, session_factory=TestingSessionLocal)
    
    manager.recover()
    assert provider.change_count == 0
    assert manager.state == AccessState.AVAILABLE

def test_noop_network_provider_behavior(clean_db):
    provider = NoopNetworkProvider(context_id="static_env", connected=True)
    assert provider.current_context() == "static_env"
    
    # change_context always fails for Noop
    assert provider.change_context() is False
    assert provider.validate_connectivity() is True
    
    manager = SourceAccessManager(provider, session_factory=TestingSessionLocal)
    manager.report_network_error()
    manager.recover()
    
    # Because change_context fails on Noop, it becomes UNAVAILABLE
    assert manager.state == AccessState.UNAVAILABLE

def test_network_context_tracking(clean_db):
    provider = MockNetworkProvider(start_context="IP_1")
    manager = SourceAccessManager(provider, session_factory=TestingSessionLocal)
    
    assert manager.current_context == "IP_1"
    
    manager.report_network_error()
    manager.recover()
    
    assert manager.current_context == "mock_context_2"
    
def test_failed_recovery_does_not_update_context(clean_db):
    provider = MockNetworkProvider(start_context="IP_1")
    provider.will_fail_change = True
    manager = SourceAccessManager(provider, session_factory=TestingSessionLocal)
    
    manager.report_network_error()
    manager.recover()
    
    assert manager.current_context == "IP_1"
    
def test_unavailable_recovery(clean_db):
    provider = MockNetworkProvider()
    provider.will_fail_change = True
    manager = SourceAccessManager(provider, session_factory=TestingSessionLocal)
    
    manager.report_network_error()
    manager.recover()
    assert manager.state == AccessState.UNAVAILABLE
    
    # The worker/system can call report_network_error again when UNAVAILABLE to restart recovery?
    # No, our system only transitions to NETWORK_ERROR from AVAILABLE.
    # To recover from UNAVAILABLE, we can just call recover() directly because it handles UNAVAILABLE
    provider.will_fail_change = False
    
    db = TestingSessionLocal()
    row = db.query(NetworkState).filter_by(id=1).first()
    row.state = AccessState.NETWORK_ERROR.value
    db.commit()
    db.close()

    manager.recover()
    
    assert provider.change_count == 1
    assert manager.state == AccessState.AVAILABLE

def test_stale_recovery_takeover(clean_db):
    provider = MockNetworkProvider()
    manager = SourceAccessManager(provider, session_factory=TestingSessionLocal)
    
    # Simulate a crashed process that left state in RECOVERING over 120 seconds ago
    db = TestingSessionLocal()
    row = db.query(NetworkState).filter_by(id=1).first()
    row.state = AccessState.RECOVERING.value
    from datetime import datetime, timedelta
    row.recovery_started_at = datetime.utcnow() - timedelta(seconds=130)
    db.commit()
    db.close()
    
    # The current manager should take over
    manager.recover()
    
    assert provider.change_count == 1
    assert manager.state == AccessState.AVAILABLE

def test_concurrent_recovery_waits(clean_db):
    provider = MockNetworkProvider()
    manager = SourceAccessManager(provider, session_factory=TestingSessionLocal)
    
    # Simulate an ACTIVE recovery (not stale)
    db = TestingSessionLocal()
    row = db.query(NetworkState).filter_by(id=1).first()
    row.state = AccessState.RECOVERING.value
    from datetime import datetime
    row.recovery_started_at = datetime.utcnow()
    db.commit()
    db.close()
    
    # The current manager should observe it and wait (return without changing context)
    manager.recover()
    
    assert provider.change_count == 0
    assert manager.state == AccessState.RECOVERING # Still recovering

def test_truncated_never_invokes_network_provider(clean_db):
    # TRUNCATED is a successful domain response, SourceAccessManager stays AVAILABLE
    provider = MockNetworkProvider()
    manager = SourceAccessManager(provider, session_factory=TestingSessionLocal)
    
    assert manager.state == AccessState.AVAILABLE
    manager.recover() # shouldn't do anything because it's AVAILABLE
    assert provider.change_count == 0

def test_advisory_lock_lifetime(clean_db):
    import threading
    import time
    from sqlalchemy import text
    
    class SlowMockNetworkProvider(MockNetworkProvider):
        def change_context(self) -> bool:
            # Simulate a slow physical network switch (1.5 seconds)
            time.sleep(1.5)
            self.change_count += 1
            self._current_context = "slow_recovered_context"
            return True

    provider1 = SlowMockNetworkProvider()
    manager1 = SourceAccessManager(provider1, session_factory=TestingSessionLocal)
    manager1.report_network_error()
    
    provider2 = SlowMockNetworkProvider()
    manager2 = SourceAccessManager(provider2, session_factory=TestingSessionLocal)
    
    # Run manager1.recover in a background thread
    t1 = threading.Thread(target=manager1.recover)
    t1.start()
    
    # Wait slightly to ensure t1 acquires the lock and enters change_context sleep
    time.sleep(0.5)
    
    # While t1 is sleeping, try to acquire the lock directly using another DB session
    db = TestingSessionLocal()
    # It should fail because t1 holds the lock
    lock_result = db.execute(text(f"SELECT pg_try_advisory_lock({SourceAccessManager.ADVISORY_LOCK_ID})")).scalar()
    if lock_result:
        # If we got it, it means the lock wasn't held during the network switch!
        db.execute(text(f"SELECT pg_advisory_unlock({SourceAccessManager.ADVISORY_LOCK_ID})"))
        db.commit()
    db.close()
    
    assert not lock_result, "Another process was able to acquire the advisory lock while the physical recovery was executing!"
    
    # Also verify that manager2 just skips instead of blocking or taking over
    manager2.recover()
    assert provider2.change_count == 0
    
    # Wait for t1 to finish
    t1.join()
    assert provider1.change_count == 1
    assert manager1.state == AccessState.AVAILABLE
