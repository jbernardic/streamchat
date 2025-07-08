"""
StreamChat - A unified library for pulling chat from livestreams.

Supports YouTube, Twitch, and Kick platforms.
"""

from .wrapper import StreamChatClient
from .exceptions import StreamChatError, PlatformNotSupportedError, AuthenticationError

__version__ = "0.1.0"
__all__ = ["StreamChatClient", "StreamChatError", "PlatformNotSupportedError", "AuthenticationError"]