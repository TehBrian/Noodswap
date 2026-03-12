import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


# Guards duplicate in-flight executions for the same user+action key.
_ACTIVE_KEYS: set[tuple[int, str]] = set()
_REGISTRY_LOCK = asyncio.Lock()


@asynccontextmanager
async def command_execution_gate(user_id: int, action_key: str) -> AsyncIterator[bool]:
    key = (user_id, action_key)
    entered = False

    async with _REGISTRY_LOCK:
        if key not in _ACTIVE_KEYS:
            _ACTIVE_KEYS.add(key)
            entered = True

    try:
        yield entered
    finally:
        if entered:
            async with _REGISTRY_LOCK:
                _ACTIVE_KEYS.discard(key)
