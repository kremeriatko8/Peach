"""Public HTTP Lambda entry point; migrations use app.migration_handler instead."""

import asyncio
from typing import Any

from mangum import Mangum

from app.main import app

# Mangum calls asyncio.get_event_loop(), which on Python 3.14 raises when no
# loop is set. Own one loop for the life of the execution environment, and set
# it again before every HTTP invocation.
_loop = asyncio.new_event_loop()
_asgi = Mangum(app, lifespan="off")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    asyncio.set_event_loop(_loop)
    return _asgi(event, context)
