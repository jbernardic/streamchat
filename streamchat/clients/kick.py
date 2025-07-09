"""
Kick chat client implementation using WebSocket and Pusher protocol.
"""

import asyncio
import json
from typing import AsyncGenerator, Optional, Dict, Any, List
from datetime import datetime
import aiohttp
import cloudscraper
import websockets
from ..base import BaseChatClient, ChatMessage
from ..exceptions import StreamChatError, ConnectionError, StreamNotFoundError
import ua_generator


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
        self.pusher_app_key = "32cbd69e4b950bf97679"
        
    def _extract_channel_name(self, stream_id: str) -> str:
        # Extract channel name from URL
        parts = stream_id.split('/')
        return parts[-1]
        
    async def connect(self) -> None:
        """Connect to Kick chat WebSocket."""

        self.ua = ua_generator.generate()
        self.headers = {
            "Accept": "application/json",
            "Alt-Used": "kick.com",
            "Priority": "u=0, i",
            "Connection": "keep-alive",
            "User-Agent": self.ua.text
        }

        self.session = cloudscraper.CloudScraper()
        
        # Get chat room ID
        self._get_chat_room_id()
        
        # Connect to WebSocket
        await self._connect_websocket()
        
        self.is_connected = True
        
    async def disconnect(self) -> None:
        """Disconnect from Kick chat."""
        if self.websocket:
            await self.websocket.close()
            
        if self.session:
            self.session.close()
            
        self.is_connected = False
        
    def _get_chat_room_id(self) -> None:
        """Get the chat room ID for the channel."""
        url = f"https://kick.com/api/v1/channels/{self.channel}"
        try:
            with self.session.get(url, headers=self.headers) as response:
                if response.status_code == 404:
                    raise StreamNotFoundError(f"Channel not found: {self.channel}")
                elif response.status_code != 200:
                    raise StreamChatError(f"Failed to get channel info: {response.status_code}")
                    
                data = response.json()
                self.chat_room_id = data.get('chatroom', {}).get('id')
                
                if not self.chat_room_id:
                    raise StreamChatError("No chat room found for this channel")
                    
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Kick API: {e}")
            
    async def _connect_websocket(self) -> None:
        """Connect to Kick WebSocket using Pusher protocol."""
        websocket_url = (
            f"wss://ws-us2.pusher.com/app/{self.pusher_app_key}"
            "?protocol=7&client=js&flash=false"
        )

        
        try:
            self.websocket = await websockets.connect(websocket_url)
            
            subscribe_data = {
                "event": "pusher:subscribe",
                "data": {
                    "channel": f"chatrooms.{self.chat_room_id}.v2",
                    "auth": ""
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
                    # Parse the outer event structure first
                    event_data = json.loads(message)
                    
                    # Handle ping/pong
                    if event_data.get('event') == 'pusher:ping':
                        await self._send_pong()
                        continue
                    
                    # Check if this is a chat message event
                    if event_data.get('event') and 'ChatMessageEvent' in event_data.get('event', ''):
                        # Parse the inner message data (like Go implementation)
                        inner_data = json.loads(event_data.get('data', '{}'))
                        chat_message = self._parse_chat_message(inner_data)
                        if chat_message:
                            yield chat_message
                        
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    continue

        except websockets.exceptions.ConnectionClosed as e:
            self.is_connected = False
            # Try to reconnect like Go version
            try:
                await self._connect_websocket()
                self.is_connected = True
            except:
                raise StreamChatError(f"WebSocket connection closed: {e}")
        except Exception as e:
            raise StreamChatError(f"Error listening to messages: {e}")
            
            
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
        
        # Extract badges from identity.badges like Go reference
        badge_list = identity.get('badges', [])
        for badge in badge_list:
            if isinstance(badge, dict):
                badge_type = badge.get('type', '')
                if badge_type:
                    badges.append(badge_type)
        
        # Add color badge if present
        if identity.get('color'):
            badges.append('colored_name')
            
        return badges
        
    def _is_moderator(self, user: Dict[str, Any]) -> bool:
        """Check if user is a moderator."""
        badges = self._extract_badges(user)
        return "moderator" in badges
        
    def _is_subscriber(self, user: Dict[str, Any]) -> bool:
        """Check if user is a subscriber."""
        badges = self._extract_badges(user)
        return "subscriber" in badges
        
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