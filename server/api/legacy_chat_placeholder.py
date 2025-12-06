from fastapi import APIRouter, Request, Response
import json
from server.api.chat import run_chat

router = APIRouter()

# Legacy compatibility for ChatPage.tsx
# It might call /api/chat or /api/chat/stream directly
# Check routes.py to see what ChatPage calls

# Looking at ChatPage.tsx source (from grep):
# const r = await fetch("/api/chat/sessions");
# ...
# In ChatPage.tsx implementation of stream:
# it probably posts to /api/chat/stream

# We need to ensure existing /api/chat/stream still works or redirects to new graph run
# server/routes.py defines /chat/stream. We updated ingest_pdf, but did we update chat?
# We should update server/routes.py chat_stream to use the new QA Graph if configured.

# In server/routes.py:
# @secure_router.post("/chat/stream")
# async def chat_stream(...)

# We will patch server/routes.py again to redirect chat_stream to new QA Graph logic if needed
# Or we can just keep them separate for now if ChatPage uses legacy endpoints.
# But the goal is "Fusion".

# Let's update server/routes.py to use new retrieval graph.

