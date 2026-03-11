"""Compatibility patches applied once at startup.

``asyncio.iscoroutinefunction`` is patched to use ``inspect.iscoroutinefunction``
because Python 3.14 removed the asyncio version and discord.py's internal
decorator machinery calls ``asyncio.iscoroutinefunction`` to recognise async
callbacks.  Without this patch, View button callbacks fail to register.

This module must be imported before any discord import.
"""
import asyncio
import inspect

asyncio.iscoroutinefunction = inspect.iscoroutinefunction  # type: ignore[assignment]
