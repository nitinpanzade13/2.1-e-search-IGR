from typing import Protocol

class CaptchaSolver(Protocol):
    """
    Protocol defining the boundary for CAPTCHA solving.
    The client passes image bytes and expects a solved string in return.
    """
    def solve(self, image_bytes: bytes) -> str:
        ...
