"""
Example usage of the StreamChat library.

This script demonstrates how to use the library to connect to various
streaming platforms and listen for chat messages.
"""

import asyncio
import os
from streamchat import StreamChatClient
import dotenv

dotenv.load_dotenv()

async def example(stream_url: str):

    config = {
        'youtube_api_key': os.getenv('YOUTUBE_API_KEY'),
        'twitch_oauth_token': os.getenv('TWITCH_OAUTH_TOKEN'),
        'twitch_username': os.getenv('TWITCH_USERNAME'),
        'poll_interval': 5,  # For YouTube polling
    }
    
    try:
        # Create client - platform is auto-detected
        client = StreamChatClient(stream_url, **config)
        
        print(f"Detected platform: {client.get_platform()}")
        print(f"Connecting to: {stream_url}")
        
        # Use as context manager for automatic cleanup
        async with client:
            print("Connected! Listening for messages...")
            async for message in client.listen():
                print(f"[{message.platform}] {message.author}: {message.content}")

                print(f"  └─ Badges: {message.badges}")
                print(f"  └─ Emotes: {message.emotes}")
                print(f"  └─ Timestamp: {message.timestamp}")
                print(f"  └─ Moderator: {message.is_moderator}")
                print(f"  └─ Subscriber: {message.is_subscriber}")
                print(f"  └─ Color: {message.color}")
                    
    except Exception as e:
        print(f"Error: {e}")

async def main():
    await example("https://kick.com/chips")

if __name__ == "__main__":
    # Set up environment variables (optional)
    print("Environment variables you can set:")
    print("- YOUTUBE_API_KEY: Your YouTube Data API key")
    print("- TWITCH_OAUTH_TOKEN: Your Twitch OAuth token")
    print("- TWITCH_USERNAME: Your Twitch username")
    print()
    
    # Run the examples
    asyncio.run(main())