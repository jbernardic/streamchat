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
            stream_id: YouTube video URL or Youtube channel URL
            api_key: YouTube Data API key
            **kwargs: Additional configuration
        """
        super().__init__(stream_id, **kwargs)
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.stream_id = stream_id
        self.video_id = None
        self.chat_id: Optional[str] = None
        self.next_page_token: Optional[str] = None
        self.poll_interval = kwargs.get('poll_interval', 2)  # seconds
        
    async def _get_video_id(self) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        # Extract video ID from URL
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:watch\?v=)([0-9A-Za-z_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, self.stream_id)
            if match:
                return match.group(1)
        
        # If no video ID found, this might be a channel URL
        channel_id = await self._get_channel_id(self.stream_id)
        if not channel_id:
            raise StreamNotFoundError("No video ID or channel ID found")
        
        return await self._get_video_id_from_channel(channel_id)
        
    async def _get_video_id_from_channel(self, channel_id: str) -> Optional[str]:
        """Gets live video ID with most viewers from a channel."""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        # Search for live streams from the channel
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'snippet',
            'channelId': channel_id,
            'type': 'video',
            'eventType': 'live',
            'order': 'date',
            'maxResults': 50,  # Get more results to find the one with most viewers
            'key': self.api_key
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 401:
                    raise AuthenticationError("Invalid YouTube API key")
                elif response.status != 200:
                    raise StreamChatError(f"Failed to search for live videos: {response.status}")
                    
                data = await response.json()
                
                if not data.get('items'):
                    raise StreamNotFoundError(f"No live streams found for channel: {channel_id}")
                
                # Get video IDs to fetch detailed statistics
                video_ids = [item['id']['videoId'] for item in data['items']]

                if len(video_ids) == 1:
                    return video_ids[0]
                
                # Get video statistics including concurrent viewer count
                stats_url = "https://www.googleapis.com/youtube/v3/videos"
                stats_params = {
                    'part': 'liveStreamingDetails,statistics',
                    'id': ','.join(video_ids),
                    'key': self.api_key
                }
                
                async with self.session.get(stats_url, params=stats_params) as stats_response:
                    if stats_response.status != 200:
                        # Fallback to first live video if we can't get stats
                        return video_ids[0]
                    
                    stats_data = await stats_response.json()
                    
                    best_video = None
                    max_viewers = 0
                    
                    for video in stats_data.get('items', []):
                        live_details = video.get('liveStreamingDetails', {})
                        concurrent_viewers = int(live_details.get('concurrentViewers', 0))
                        
                        if concurrent_viewers > max_viewers:
                            max_viewers = concurrent_viewers
                            best_video = video['id']
                    
                    # Return the video with most viewers, or first one if no viewer data
                    return best_video or video_ids[0]
                
        except Exception as e:
            raise StreamChatError(f"Error getting livestream with most viewers from channel: {e}")

    async def _get_channel_id(self, stream_id):
        """Extract channel ID from YouTube URL or resolve handle to channel ID."""
        pattern = re.compile(r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/(?:@([a-zA-Z0-9._-]+)|channel\/(UC[a-zA-Z0-9_-]{22}))')
        match = pattern.match(stream_id)
        
        if not match:
            return None
            
        handle = match.group(1)
        channel_id = match.group(2)
        
        if channel_id:
            return channel_id
        elif handle:
            # Resolve handle to channel ID using YouTube API
            return await self._resolve_handle_to_channel_id(handle)
        
        return None
    
    async def _resolve_handle_to_channel_id(self, handle: str) -> Optional[str]:
        """Resolve a YouTube handle (@username) to channel ID using YouTube API."""
        if not self.api_key:
            raise AuthenticationError("YouTube API key is required to resolve handles")
            
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            'part': 'id',
            'forHandle': handle,
            'key': self.api_key
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 401:
                    raise AuthenticationError("Invalid YouTube API key")
                elif response.status != 200:
                    raise StreamChatError(f"Failed to resolve handle: {response.status}")
                    
                data = await response.json()
                
                if not data.get('items'):
                    raise StreamNotFoundError(f"Channel not found for handle: @{handle}")
                    
                return data['items'][0]['id']
                
        except Exception as e:
            raise StreamChatError(f"Error resolving handle to channel ID: {e}")
        
    async def connect(self) -> None:
        """Connect to YouTube chat stream."""
        if not self.api_key:
            raise AuthenticationError("YouTube API key is required")
            
        self.session = aiohttp.ClientSession()
        
        # Get video ID
        self.video_id = await self._get_video_id()

        # Get live chat ID
        self.chat_id = await self._get_live_chat_id()
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
                
            return live_details['activeLiveChatId']
            
    async def listen(self) -> AsyncGenerator[ChatMessage, None]:
        """Listen for YouTube chat messages."""
        if not self.is_connected:
            raise StreamChatError("Not connected to chat stream")
        
        now = datetime.now()

        while self.is_connected:
            try:
                messages = await self._fetch_messages()
                for message in messages:
                    if message.timestamp > now:
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
                timestamp=datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00')).astimezone().replace(tzinfo=None),
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