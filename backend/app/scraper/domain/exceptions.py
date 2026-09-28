class IGRBaseException(Exception):
    """Base exception for Stage 1 IGR operations."""
    def __init__(self, message: str, failure_category: str, retryable: bool):
        super().__init__(message)
        self.message = message
        self.failure_category = failure_category
        self.retryable = retryable

class IGRSourceError(IGRBaseException):
    """General error from the IGR source."""
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message, failure_category="SOURCE_ERROR", retryable=retryable)

class IGRNetworkError(IGRBaseException):
    """Network-level error when communicating with IGR."""
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message, failure_category="NETWORK_ERROR", retryable=retryable)

class IGRSessionError(IGRBaseException):
    """Error related to HTTP session, CSRF, or auth state."""
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message, failure_category="SESSION_ERROR", retryable=retryable)

class IGRCaptchaError(IGRBaseException):
    """Error related to solving or validating a CAPTCHA."""
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message, failure_category="CAPTCHA_ERROR", retryable=retryable)

class IGRRateLimitError(IGRBaseException):
    """Error indicating the daily source IP limit was reached."""
    def __init__(self, message: str = "Rate limit exceeded", retryable: bool = True):
        super().__init__(message, failure_category="RATE_LIMIT_ERROR", retryable=retryable)

class IGRValidationError(IGRBaseException):
    """Validation error returned by the IGR source (e.g. invalid parameters)."""
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message, failure_category="VALIDATION_ERROR", retryable=retryable)

class IGRUnexpectedResponseError(IGRBaseException):
    """Error when the source returns an HTTP response structure we do not recognize."""
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message, failure_category="UNEXPECTED_RESPONSE_ERROR", retryable=retryable)

class IGRParserError(IGRBaseException):
    """Error extracting structured data from raw HTML."""
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message, failure_category="PARSER_ERROR", retryable=retryable)

class ArtifactStorageError(IGRBaseException):
    """Error saving or reading raw HTML artifacts."""
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message, failure_category="ARTIFACT_STORAGE_ERROR", retryable=retryable)

class IdentityResolutionError(IGRBaseException):
    """Error making a safe deduplication/identity decision."""
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message, failure_category="IDENTITY_RESOLUTION_ERROR", retryable=retryable)

class SourceAccessUnavailable(IGRBaseException):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message, failure_category="SOURCE_ACCESS_UNAVAILABLE", retryable=retryable)
