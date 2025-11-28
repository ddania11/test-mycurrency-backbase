class APIClientError(Exception):
    """Base exception for all API client errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class APIConnectionError(APIClientError):
    """Raised when there's a connection error with the API."""

    pass


class APITimeoutError(APIClientError):
    """Raised when the API request times out."""

    pass


class APIResponseError(APIClientError):
    """Raised when the API returns an invalid or unexpected response."""

    pass


class APIAuthenticationError(APIClientError):
    """Raised when authentication with the API fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class APIRateLimitError(APIClientError):
    """Raised when the API rate limit is exceeded."""

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: int | None = None
    ):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class APINotFoundError(APIClientError):
    """Raised when the requested resource is not found."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)
