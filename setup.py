"""
Setup script for StreamChat library.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="streamchat",
    version="0.1.0",
    author="Jan Bernardic",
    author_email="janbernardic1@gmail.com",
    description="A library for pulling chat from livestreams (YouTube, Twitch, Kick)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jbernardic/streamchat",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Chat",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Multimedia :: Video :: Display",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=[
        "aiohttp>=3.8.0",
        "websockets>=10.0",
    ],
    keywords="chat, livestream, youtube, twitch, kick, streaming, realtime",
    project_urls={
        "Bug Reports": "https://github.com/jbernardic/streamchat/issues",
        "Source": "https://github.com/jbernardic/streamchat",
    },
)