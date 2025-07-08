"""
Abstract base class for chat clients.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatMessage:
    """Represents a chat message from any platform."""
    id: str
    author: str
    content: str
    timestamp: datetime
    platform: str
    author_id: Optional[str] = None
    badges: Optional[List[str]] = None
    emotes: Optional[List[Dict[str, Any]]] = None
    color: Optional[str] = None
    is_moderator: bool = False
    is_subscriber: bool = False
    is_vip: bool = False
    raw_data: Optional[Dict[str, Any]] = None


class BaseChatClient(ABC):
    """Abstract base class for platform-specific chat clients."""
    
    def __init__(self, stream_id: str, **kwargs):
        """
        Initialize the chat client.
        
        Args:
            stream_id: The stream identifier (URL, channel name, etc.)
            **kwargs: Platform-specific configuration
        """
        self.stream_id = stream_id
        self.config = kwargs
        self.is_connected = False
        
    @abstractmethod
    async def connect(self) -> None:
        """Connect to the chat stream."""
        pass
        
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the chat stream."""
        pass
        
    @abstractmethod
    async def listen(self) -> AsyncGenerator[ChatMessage, None]:
        """
        Listen for chat messages.
        
        Yields:
            ChatMessage: Parsed chat messages
        """
        pass
        
    @abstractmethod
    def get_platform_name(self) -> str:
        """Return the platform name."""
        pass
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()