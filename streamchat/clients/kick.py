"""
Kick chat client implementation using WebSocket and Pusher protocol.
"""

import asyncio
import json
from typing import AsyncGenerator, Optional, Dict, Any, List
from datetime import datetime
import aiohttp
import websockets
from ..base import BaseChatClient, ChatMessage
from ..exceptions import StreamChatError, ConnectionError, StreamNotFoundError


class KickChatClient(BaseChatClient):
    """Kick chat client using WebSocket and Pusher protocol."""
    
    def __init__(self, stream_id: str, **kwargs):
        """
        Initialize Kick chat client.
        
        Args:
            stream_id: Kick channel URL
            **kwargs: Additional configuration
        """
        super().__init__(stream_id, **kwargs)
        self.channel = self._extract_channel_name(stream_id)
        self.websocket = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.chat_room_id: Optional[int] = None
        self.pusher_app_key = "eb1d5f283081a78b932c"  # Kick's public Pusher key
        
    def _extract_channel_name(self, stream_id: str) -> str:
        # Extract channel name from URL
        parts = stream_id.split('/')
        return parts[-1]
        
    async def connect(self) -> None:
        """Connect to Kick chat WebSocket."""
        self.session = aiohttp.ClientSession()
        
        # Get chat room ID
        await self._get_chat_room_id()
        
        # Connect to WebSocket
        await self._connect_websocket()
        
        self.is_connected = True
        
    async def disconnect(self) -> None:
        """Disconnect from Kick chat."""
        if self.websocket:
            await self.websocket.close()
            
        if self.session:
            await self.session.close()
            
        self.is_connected = False
        
    async def _get_chat_room_id(self) -> None:
        """Get the chat room ID for the channel."""
        url = f"https://kick.com/api/v2/channels/{self.channel}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 404:
                    raise StreamNotFoundError(f"Channel not found: {self.channel}")
                elif response.status != 200:
                    raise StreamChatError(f"Failed to get channel info: {response.status}")
                    
                data = await response.json()
                self.chat_room_id = data.get('chatroom', {}).get('id')
                
                if not self.chat_room_id:
                    raise StreamChatError("No chat room found for this channel")
                    
        except aiohttp.ClientError as e:
            raise ConnectionError(f"Failed to connect to Kick API: {e}")
            
    async def _connect_websocket(self) -> None:
        """Connect to Kick WebSocket using Pusher protocol."""
        websocket_url = f"wss://ws-us2.pusher.com/app/{self.pusher_app_key}?protocol=7&client=js&version=7.0.3&flash=false"
        
        try:
            self.websocket = await websockets.connect(websocket_url)
            
            # Send connection message
            connection_data = {
                "event": "pusher:connection_established",
                "data": {}
            }
            
            # Subscribe to chat channel
            subscribe_data = {
                "event": "pusher:subscribe",
                "data": {
                    "channel": f"chatrooms.{self.chat_room_id}.v2"
                }
            }
            
            await self.websocket.send(json.dumps(subscribe_data))
            
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Kick WebSocket: {e}")
            
    async def listen(self) -> AsyncGenerator[ChatMessage, None]:
        """Listen for Kick chat messages."""
        if not self.is_connected:
            raise StreamChatError("Not connected to chat stream")
            
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    chat_message = self._parse_message(data)
                    if chat_message:
                        yield chat_message
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    # Log error but continue listening
                    continue
                    
        except websockets.exceptions.ConnectionClosed:
            self.is_connected = False
            raise StreamChatError("WebSocket connection closed")
        except Exception as e:
            raise StreamChatError(f"Error listening to messages: {e}")
            
    def _parse_message(self, data: Dict[str, Any]) -> Optional[ChatMessage]:
        """Parse WebSocket message into ChatMessage."""
        try:
            # Handle different event types
            if data.get('event') == 'App\\Events\\ChatMessageEvent':
                message_data = json.loads(data.get('data', '{}'))
                return self._parse_chat_message(message_data)
            elif data.get('event') == 'pusher:ping':
                # Send pong response
                asyncio.create_task(self._send_pong())
                
            return None
            
        except (json.JSONDecodeError, KeyError):
            return None
            
    def _parse_chat_message(self, message_data: Dict[str, Any]) -> Optional[ChatMessage]:
        """Parse chat message data."""
        try:
            user = message_data.get('sender', {})
            content = message_data.get('content', '')
            
            # Skip system messages
            if not user or not content:
                return None
                
            return ChatMessage(
                id=str(message_data.get('id', '')),
                author=user.get('username', 'Unknown'),
                content=content,
                timestamp=datetime.now(),  # Kick doesn't provide precise timestamps
                platform='kick',
                author_id=str(user.get('id', '')),
                badges=self._extract_badges(user),
                color=user.get('identity', {}).get('color'),
                is_moderator=self._is_moderator(user),
                is_subscriber=self._is_subscriber(user),
                raw_data=message_data
            )
            
        except KeyError:
            return None
            
    def _extract_badges(self, user: Dict[str, Any]) -> List[str]:
        """Extract user badges."""
        badges = []
        identity = user.get('identity', {})
        
        if identity.get('color'):
            badges.append('colored_name')
            
        # Check for verified badge
        if user.get('verified'):
            badges.append('verified')
            
        # Check for staff/moderator badges
        if self._is_moderator(user):
            badges.append('moderator')
            
        if self._is_subscriber(user):
            badges.append('subscriber')
            
        return badges
        
    def _is_moderator(self, user: Dict[str, Any]) -> bool:
        """Check if user is a moderator."""
        # This might need adjustment based on Kick's actual API response
        return user.get('is_moderator', False)
        
    def _is_subscriber(self, user: Dict[str, Any]) -> bool:
        """Check if user is a subscriber."""
        # This might need adjustment based on Kick's actual API response
        return user.get('is_subscriber', False)
        
    async def _send_pong(self) -> None:
        """Send pong response to ping."""
        if self.websocket:
            pong_data = {
                "event": "pusher:pong",
                "data": {}
            }
            await self.websocket.send(json.dumps(pong_data))
            
    def get_platform_name(self) -> str:
        """Return the platform name."""
        return "kick"