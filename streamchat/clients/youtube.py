"""
YouTube chat client implementation.
"""

import asyncio
import json
import re
from typing import AsyncGenerator, Optional, Dict, Any
from datetime import datetime
import aiohttp
from ..base import BaseChatClient, ChatMessage
from ..exceptions import StreamChatError, AuthenticationError, StreamNotFoundError


class YouTubeChatClient(BaseChatClient):
    """YouTube chat client using YouTube Data API and live chat polling."""
    
    def __init__(self, stream_id: str, api_key: Optional[str] = None, **kwargs):
        """
        Initialize YouTube chat client.
        
        Args:
            stream_id: YouTube video URL
            api_key: YouTube Data API key
            **kwargs: Additional configuration
        """
        super().__init__(stream_id, **kwargs)
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.video_id = self._extract_video_id(stream_id)
        self.chat_id: Optional[str] = None
        self.next_page_token: Optional[str] = None
        self.poll_interval = kwargs.get('poll_interval', 2)  # seconds
        
    def _extract_video_id(self, stream_id: str) -> str:
        """Extract video ID from YouTube URL"""
        # Extract video ID from URL
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:watch\?v=)([0-9A-Za-z_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, stream_id)
            if match:
                return match.group(1)
        
    async def connect(self) -> None:
        """Connect to YouTube chat stream."""
        if not self.api_key:
            raise AuthenticationError("YouTube API key is required")
            
        self.session = aiohttp.ClientSession()
        
        # Get live chat ID
        await self._get_live_chat_id()
        self.is_connected = True
        
    async def disconnect(self) -> None:
        """Disconnect from YouTube chat stream."""
        if self.session:
            await self.session.close()
        self.is_connected = False
        
    async def _get_live_chat_id(self) -> None:
        """Get the live chat ID for the video."""
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            'part': 'liveStreamingDetails',
            'id': self.video_id,
            'key': self.api_key
        }
        
        async with self.session.get(url, params=params) as response:
            if response.status == 401:
                raise AuthenticationError("Invalid YouTube API key")
            elif response.status != 200:
                raise StreamChatError(f"Failed to get video info: {response.status}")
                
            data = await response.json()
            
            if not data.get('items'):
                raise StreamNotFoundError(f"Video not found: {self.video_id}")
                
            item = data['items'][0]
            live_details = item.get('liveStreamingDetails', {})
            
            if 'activeLiveChatId' not in live_details:
                raise StreamChatError("No active live chat found for this video")
                
            self.chat_id = live_details['activeLiveChatId']
            
    async def listen(self) -> AsyncGenerator[ChatMessage, None]:
        """Listen for YouTube chat messages."""
        if not self.is_connected:
            raise StreamChatError("Not connected to chat stream")
            
        while self.is_connected:
            try:
                messages = await self._fetch_messages()
                for message in messages:
                    yield message
                    
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                raise StreamChatError(f"Error fetching messages: {e}")
                
    async def _fetch_messages(self) -> list[ChatMessage]:
        """Fetch new chat messages from YouTube API."""
        url = "https://www.googleapis.com/youtube/v3/liveChat/messages"
        params = {
            'liveChatId': self.chat_id,
            'part': 'snippet,authorDetails',
            'key': self.api_key
        }
        
        if self.next_page_token:
            params['pageToken'] = self.next_page_token
            
        async with self.session.get(url, params=params) as response:
            if response.status != 200:
                raise StreamChatError(f"Failed to fetch messages: {response.status}")
                
            data = await response.json()
            
            self.next_page_token = data.get('nextPageToken')
            self.poll_interval = data.get('pollingIntervalMillis', 2000) / 1000
            
            messages = []
            for item in data.get('items', []):
                message = self._parse_message(item)
                if message:
                    messages.append(message)
                    
            return messages
            
    def _parse_message(self, item: Dict[str, Any]) -> Optional[ChatMessage]:
        """Parse a YouTube chat message."""
        try:
            snippet = item['snippet']
            author = item['authorDetails']
            
            # Skip system messages
            if snippet.get('type') != 'textMessageEvent':
                return None
                
            return ChatMessage(
                id=item['id'],
                author=author['displayName'],
                content=snippet['displayMessage'],
                timestamp=datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00')),
                platform='youtube',
                author_id=author['channelId'],
                badges=self._extract_badges(author),
                is_moderator=author.get('isChatModerator', False),
                is_subscriber=author.get('isChatSponsor', False),
                raw_data=item
            )
        except KeyError as e:
            return None
            
    def _extract_badges(self, author: Dict[str, Any]) -> list[str]:
        """Extract user badges from author details."""
        badges = []
        if author.get('isChatOwner'):
            badges.append('owner')
        if author.get('isChatModerator'):
            badges.append('moderator')
        if author.get('isChatSponsor'):
            badges.append('member')
        if author.get('isVerified'):
            badges.append('verified')
        return badges
        
    def get_platform_name(self) -> str:
        """Return the platform name."""
        return "youtube"