"""
Twitch chat client implementation using IRC protocol.
"""

import asyncio
import re
from typing import AsyncGenerator, Optional, Dict, Any, List
from datetime import datetime
from ..base import BaseChatClient, ChatMessage
from ..exceptions import StreamChatError, AuthenticationError, ConnectionError


class TwitchChatClient(BaseChatClient):
    """Twitch chat client using IRC protocol."""
    
    def __init__(self, stream_id: str, oauth_token: Optional[str] = None, **kwargs):
        """
        Initialize Twitch chat client.
        
        Args:
            stream_id: Twitch channel URL
            oauth_token: Twitch OAuth token (optional for read-only)
            **kwargs: Additional configuration
        """

        super().__init__(stream_id, **kwargs)
        self.oauth_token = oauth_token
        self.channel = self._extract_channel_name(self.stream_id)
        self.username = kwargs.get('username') or 'justinfan12345'  # Anonymous user
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.host = 'irc.chat.twitch.tv'
        self.port = 6667
        self.user_badges: Dict[str, List[str]] = {}

    def _extract_channel_name(self, stream_id: str) -> str:
        """Extract channel name from Twitch URL"""
        parts = stream_id.split('/')
        return parts[-1]
        
    async def connect(self) -> None:
        """Connect to Twitch IRC chat."""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            
            # Send authentication
            if self.oauth_token:
                await self._send_command(f"PASS oauth:{self.oauth_token}")
                await self._send_command(f"NICK {self.username}")
            else:
                await self._send_command(f"NICK {self.username}")
                
            # Request capabilities for user badges, emotes, etc.
            await self._send_command("CAP REQ :twitch.tv/tags")
            await self._send_command("CAP REQ :twitch.tv/commands")
            
            # Join channel
            await self._send_command(f"JOIN #{self.channel}")
            
            self.is_connected = True
            
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Twitch IRC: {e}")
            
    async def disconnect(self) -> None:
        """Disconnect from Twitch IRC chat."""
        if self.writer:
            await self._send_command(f"PART #{self.channel}")
            self.writer.close()
            await self.writer.wait_closed()
        self.is_connected = False
        
    async def _send_command(self, command: str) -> None:
        """Send IRC command."""
        if self.writer:
            self.writer.write(f"{command}\r\n".encode())
            await self.writer.drain()
            
    async def listen(self) -> AsyncGenerator[ChatMessage, None]:
        """Listen for Twitch chat messages."""
        if not self.is_connected:
            raise StreamChatError("Not connected to chat stream")
            
        while self.is_connected:
            try:
                line = await self.reader.readline()
                if not line:
                    break
                    
                line = line.decode('utf-8').strip()
                
                # Handle PING/PONG
                if line.startswith('PING'):
                    await self._send_command('PONG :tmi.twitch.tv')
                    continue
                    
                # Parse message
                message = self._parse_message(line)
                if message:
                    yield message
                    
            except Exception as e:
                raise StreamChatError(f"Error reading from IRC: {e}")
                
    def _parse_message(self, line: str) -> Optional[ChatMessage]:
        """Parse IRC message into ChatMessage."""
        # Handle messages with tags (user info)
        tags = {}
        if line.startswith('@'):
            tag_part, line = line[1:].split(' ', 1)
            tags = self._parse_tags(tag_part)
            
        # Parse IRC message format
        # :username!username@username.tmi.twitch.tv PRIVMSG #channel :message
        pattern = r'^:(\w+)!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #(\w+) :(.+)$'
        match = re.match(pattern, line)
        
        if not match:
            return None
            
        username, channel, content = match.groups()
        
        if channel != self.channel:
            return None
            
        return ChatMessage(
            id=tags.get('id', f"{username}_{datetime.now().timestamp()}"),
            author=tags.get('display-name', username),
            content=content,
            timestamp=datetime.now(),
            platform='twitch',
            author_id=tags.get('user-id'),
            badges=self._extract_badges(tags),
            emotes=self._extract_emotes(tags),
            color=tags.get('color'),
            is_moderator=tags.get('mod') == '1',
            is_subscriber=tags.get('subscriber') == '1',
            is_vip=tags.get('vip') == '1',
            raw_data={'tags': tags, 'raw_line': line}
        )
        
    def _parse_tags(self, tag_string: str) -> Dict[str, str]:
        """Parse IRC tags into dictionary."""
        tags = {}
        for tag in tag_string.split(';'):
            if '=' in tag:
                key, value = tag.split('=', 1)
                tags[key] = value
        return tags
        
    def _extract_badges(self, tags: Dict[str, str]) -> List[str]:
        """Extract user badges from tags."""
        badges = []
        badge_info = tags.get('badges', '')
        
        if badge_info:
            for badge in badge_info.split(','):
                if '/' in badge:
                    badge_name = badge.split('/')[0]
                    badges.append(badge_name)
                    
        return badges
        
    def _extract_emotes(self, tags: Dict[str, str]) -> List[Dict[str, Any]]:
        """Extract emote information from tags."""
        emotes = []
        emote_info = tags.get('emotes', '')
        
        if emote_info:
            # Parse emote format: emote_id:start-end,start-end/emote_id:start-end
            for emote_group in emote_info.split('/'):
                if ':' in emote_group:
                    emote_id, positions = emote_group.split(':', 1)
                    for position in positions.split(','):
                        if '-' in position:
                            start, end = position.split('-')
                            emotes.append({
                                'id': emote_id,
                                'start': int(start),
                                'end': int(end)
                            })
                            
        return emotes
        
    def get_platform_name(self) -> str:
        """Return the platform name."""
        return "twitch"