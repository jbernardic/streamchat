"""
Unified wrapper for all chat clients.
"""

import re
from typing import AsyncGenerator, Optional, Dict, Any, Type
from .base import BaseChatClient, ChatMessage
from .clients import YouTubeChatClient, TwitchChatClient, KickChatClient
from .exceptions import PlatformNotSupportedError, StreamChatError


class StreamChatClient:
    """
    Unified client for accessing chat from multiple streaming platforms.
    
    Automatically detects the platform from the stream URL and uses the
    appropriate client implementation.
    """
    
    PLATFORM_CLIENTS: Dict[str, Type[BaseChatClient]] = {
        'youtube': YouTubeChatClient,
        'twitch': TwitchChatClient,
        'kick': KickChatClient
    }
    
    def __init__(self, stream_url: str, **kwargs):
        """
        Initialize the unified chat client.
        
        Args:
            stream_url: URL or identifier for the stream
            **kwargs: Platform-specific configuration options
                     - youtube_api_key: YouTube Data API key
                     - twitch_oauth_token: Twitch OAuth token
                     - twitch_username: Twitch username
                     - poll_interval: Polling interval for YouTube (seconds)
        """
        self.stream_url = stream_url
        self.platform = self._detect_platform(stream_url)
        self.config = kwargs
        self.client: Optional[BaseChatClient] = None
        
    def _detect_platform(self, stream_url: str) -> str:
        """Detect the platform from the stream URL."""
        url_lower = stream_url.lower()
        
        # YouTube detection
        if any(domain in url_lower for domain in ['youtube.com', 'youtu.be']):
            return 'youtube'
            
        # Twitch detection
        if 'twitch.tv' in url_lower:
            return 'twitch'
            
        # Kick detection
        if 'kick.com' in url_lower:
            return 'kick'
            
        # Try to guess based on URL patterns if no domain match
        # YouTube video ID pattern
        if re.match(r'^[a-zA-Z0-9_-]{11}$', stream_url):
            return 'youtube'
            
        # Twitch channel name pattern (no special characters except underscore)
        if re.match(r'^[a-zA-Z0-9_]+$', stream_url) and len(stream_url) > 2:
            return 'twitch'  # Default to Twitch for simple usernames
            
        raise PlatformNotSupportedError(f"Cannot detect platform from: {stream_url}")
        
    async def connect(self) -> None:
        """Connect to the chat stream."""
        if self.platform not in self.PLATFORM_CLIENTS:
            raise PlatformNotSupportedError(f"Platform '{self.platform}' is not supported")
            
        client_class = self.PLATFORM_CLIENTS[self.platform]
        
        # Extract platform-specific configuration
        client_config = self._get_platform_config()
        
        # Create and connect client
        self.client = client_class(self.stream_url, **client_config)
        await self.client.connect()
        
    async def disconnect(self) -> None:
        """Disconnect from the chat stream."""
        if self.client:
            await self.client.disconnect()
            
    async def listen(self) -> AsyncGenerator[ChatMessage, None]:
        """
        Listen for chat messages from the stream.
        
        Yields:
            ChatMessage: Parsed chat messages from the stream
        """
        if not self.client:
            raise StreamChatError("Not connected. Call connect() first.")
            
        async for message in self.client.listen():
            yield message
            
    def _get_platform_config(self) -> Dict[str, Any]:
        """Extract platform-specific configuration from general config."""
        config = {}
        
        if self.platform == 'youtube':
            if 'youtube_api_key' in self.config:
                config['api_key'] = self.config['youtube_api_key']
            if 'poll_interval' in self.config:
                config['poll_interval'] = self.config['poll_interval']
                
        elif self.platform == 'twitch':
            if 'twitch_oauth_token' in self.config:
                config['oauth_token'] = self.config['twitch_oauth_token']
            if 'twitch_username' in self.config:
                config['username'] = self.config['twitch_username']
                
        elif self.platform == 'kick':
            # Kick doesn't require additional config currently
            pass
            
        return config
        
    def get_platform(self) -> str:
        """Get the detected platform name."""
        return self.platform
        
    def get_client(self) -> Optional[BaseChatClient]:
        """Get the underlying platform-specific client."""
        return self.client
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
        
    @classmethod
    def get_supported_platforms(cls) -> list[str]:
        """Get list of supported platforms."""
        return list(cls.PLATFORM_CLIENTS.keys())
        
    @classmethod
    def create_client(cls, platform: str, stream_id: str, **kwargs) -> BaseChatClient:
        """
        Create a platform-specific client directly.
        
        Args:
            platform: Platform name ('youtube', 'twitch', 'kick')
            stream_id: Stream identifier
            **kwargs: Platform-specific configuration
            
        Returns:
            BaseChatClient: Platform-specific client instance
        """
        if platform not in cls.PLATFORM_CLIENTS:
            raise PlatformNotSupportedError(f"Platform '{platform}' is not supported")
            
        client_class = cls.PLATFORM_CLIENTS[platform]
        return client_class(stream_id, **kwargs)