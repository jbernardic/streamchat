# StreamChat

A unified Python library for pulling chat messages from livestreams across multiple platforms.

## Supported Platforms

- **YouTube** - Uses YouTube Data API v3
- **Twitch** - Uses IRC protocol
- **Kick** - Uses WebSocket with Pusher protocol

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
import asyncio
from streamchat import StreamChatClient

async def main():
    # Auto-detects platform from URL
    client = StreamChatClient("https://www.twitch.tv/sodapoppin")
    
    async with client:
        async for message in client.listen():
            print(f"{message.author}: {message.content}")

asyncio.run(main())
```

### Platform-Specific Configuration

```python
from streamchat import StreamChatClient

# YouTube (requires API key)
client = StreamChatClient(
    "https://www.youtube.com/watch?v=VIDEO_ID",
    youtube_api_key="YOUR_API_KEY"
)

# Twitch (OAuth token optional for read-only)
client = StreamChatClient(
    "https://www.twitch.tv/CHANNEL",
    twitch_oauth_token="YOUR_OAUTH_TOKEN",
    twitch_username="your_username"
)

# Kick (no auth required)
client = StreamChatClient("https://kick.com/CHANNEL")
```

### Platform-Specific Clients

```python
from streamchat.clients import YouTubeChatClient, TwitchChatClient, KickChatClient

# Use specific clients directly
youtube_client = YouTubeChatClient("STREAM_URL", api_key="YOUR_API_KEY")
twitch_client = TwitchChatClient("STREAM_URL", oauth_token="YOUR_TOKEN")
kick_client = KickChatClient("STREAM_URL")
```

## Message Object

Each message contains:

```python
@dataclass
class ChatMessage:
    id: str                    # Message ID
    author: str               # Username
    content: str              # Message content
    timestamp: datetime       # When message was sent
    platform: str             # Platform name
    author_id: str            # User ID (if available)
    badges: List[str]         # User badges (mod, subscriber, etc.)
    emotes: List[Dict]        # Emote information
    color: str                # Username color
    is_moderator: bool        # Is user a moderator
    is_subscriber: bool       # Is user a subscriber
    is_vip: bool              # Is user VIP
    raw_data: Dict            # Raw platform data
```

## Authentication

### YouTube
- Get API key from Google Cloud Console
- Enable YouTube Data API v3
- Set `youtube_api_key` parameter

### Twitch
- OAuth token optional for read-only access
- Get token from https://twitchapps.com/tmi/
- Set `twitch_oauth_token` and `twitch_username` parameters

### Kick
- No authentication required for public streams

## Error Handling

```python
from streamchat import StreamChatClient
from streamchat.exceptions import (
    StreamChatError,
    PlatformNotSupportedError,
    AuthenticationError,
    StreamNotFoundError
)

try:
    async with StreamChatClient("invalid_url") as client:
        async for message in client.listen():
            print(message.content)
except PlatformNotSupportedError:
    print("Platform not supported")
except AuthenticationError:
    print("Authentication failed")
except StreamNotFoundError:
    print("Stream not found")
except StreamChatError as e:
    print(f"General error: {e}")
```

## License

MIT License