from typing import Protocol

class NetworkProvider(Protocol):
    """
    Defines the capability to read and rotate the outbound network context.
    Implementations must be authorized to perform actual OS-level network switching.
    """
    def current_context(self) -> str:
        """Returns a stable string identifier for the current network context (e.g., interface, IP, profile name)."""
        ...

    def change_context(self) -> bool:
        """Attempts to change the network context. Returns True if successfully executed, False otherwise."""
        ...

    def validate_connectivity(self) -> bool:
        """Checks if the current network context has functional outbound connectivity."""
        ...

class NoopNetworkProvider(NetworkProvider):
    """
    A passive network provider that does not attempt to modify the operating system network.
    Useful for local testing, containerized environments, or deployments where network
    rotation is managed externally or prohibited.
    """
    def __init__(self, context_id: str = "default_context", connected: bool = True):
        self._context_id = context_id
        self._connected = connected

    def current_context(self) -> str:
        return self._context_id

    def change_context(self) -> bool:
        return False

    def validate_connectivity(self) -> bool:
        return self._connected

class MockNetworkProvider(NetworkProvider):
    """
    Simulates network changes for automated testing without triggering OS operations.
    """
    def __init__(self, start_context: str = "mock_context_1"):
        self.context = start_context
        self.connected = True
        self.will_fail_change = False
        self.will_fail_connectivity = False
        self.change_count = 0

    def current_context(self) -> str:
        return self.context

    def change_context(self) -> bool:
        if self.will_fail_change:
            return False
            
        self.change_count += 1
        self.context = f"mock_context_{self.change_count + 1}"
        return True

    def validate_connectivity(self) -> bool:
        if self.will_fail_connectivity:
            return False
        return self.connected
