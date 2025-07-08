"""
Custom exceptions for StreamChat library.
"""


class StreamChatError(Exception):
    """Base exception for all StreamChat errors."""
    pass


class PlatformNotSupportedError(StreamChatError):
    """Raised when an unsupported platform is specified."""
    pass


class AuthenticationError(StreamChatError):
    """Raised when authentication fails."""
    pass


class ConnectionError(StreamChatError):
    """Raised when connection to platform fails."""
    pass


class StreamNotFoundError(StreamChatError):
    """Raised when the specified stream is not found."""
    pass


class RateLimitError(StreamChatError):
    """Raised when rate limit is exceeded."""
    pass