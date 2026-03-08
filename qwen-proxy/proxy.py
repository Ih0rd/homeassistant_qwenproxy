#!/usr/bin/env python3
"""
Qwen OAuth → OpenAI-compatible proxy for Home Assistant addon.
Endpoint: https://portal.qwen.ai/v1/chat/completions
"""

import json
import logging
import time
from pathlib import Path
from typing import AsyncGenerator

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

OPTIONS_PATH = Path("/data/options.json")
QWEN_CHAT_URL = "https://portal.qwen.ai/v1/chat/completions"
QWEN_REFRESH_URL = "https://portal.qwen.ai/api/v1/token/refresh"

SUPPORTED_MODELS = [
    "qwen3-coder-plus",
    "qwen3-coder-flash",
    "qwen3.5-plus",
    "qwen-max",
    "qwen-plus",
]


def load_options() -> dict:
    try:
        with open(OPTIONS_PATH) as f:
            return json.load(f)
    except Exception as e:
        log.error("Cannot read options.json: %s", e)
        return {}


opts = load_options()

token_state = {
    "access_token": opts.get("access_token", ""),
    "refresh_token": opts.get("refresh_token", ""),
    "expiry_ms": opts.get("expiry_date", 0),
}

DEFAULT_MODEL = opts.get("default_model", "qwen3-coder-plus")

# ── Token refresh ─────────────────────────────────────────────────────────────


async def get_token() -> str:
    now_ms = int(time.time() * 1000)
    if token_state["expiry_ms"] and now_ms < token_state["expiry_ms"] - 300_000:
        return token_state["access_token"]

    rt = token_state["refresh_token"]
    if not rt:
        return token_state["access_token"]

    log.info("Refreshing OAuth token…")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                QWEN_REFRESH_URL,
                json={"refresh_token": rt},
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                token_state["access_token"] = data.get("access_token", token_state["access_token"])
                token_state["refresh_token"] = data.get("refresh_token", token_state["refresh_token"])
                token_state["expiry_ms"] = data.get("expiry_date", 0)
                log.info("Token refreshed OK.")
            else:
                log.warning("Token refresh failed (%s)", resp.status_code)
    except Exception as e:
        log.warning("Token refresh error: %s", e)

    return token_state["access_token"]


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Qwen OAuth Proxy", version="4.0.0")


@app.get("/health")
async def health():
    return {"status": "ok", "default_model": DEFAULT_MODEL}


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": m, "object": "model", "created": 1700000000, "owned_by": "qwen"}
            for m in SUPPORTED_MODELS
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()

    if not body.get("model"):
        body["model"] = DEFAULT_MODEL

    stream = body.get("stream", False)
    token = await get_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if stream else "application/json",
    }

    log.info("→ model=%s stream=%s", body["model"], stream)

    if stream:
        return StreamingResponse(
            _stream(body, headers),
            media_type="text/event-stream",
        )

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(QWEN_CHAT_URL, json=body, headers=headers)

    log.info("← %s", resp.status_code)

    if resp.status_code != 200:
        log.error("Qwen error %s: %s", resp.status_code, resp.text)

    return JSONResponse(content=resp.json(), status_code=resp.status_code)


async def _stream(body: dict, headers: dict) -> AsyncGenerator[bytes, None]:
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", QWEN_CHAT_URL, json=body, headers=headers) as resp:
                async for line in resp.aiter_lines():
                    if line:
                        yield (line + "\n\n").encode()
    except Exception as e:
        log.error("Stream error: %s", e)
        yield b"data: [DONE]\n\n"


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    at = token_state["access_token"]
    if not at:
        log.error("access_token is empty! Configure it in addon options.")
    else:
        log.info("Qwen OAuth Proxy v4 starting on port 8080")
        log.info("Default model: %s", DEFAULT_MODEL)
        log.info("Token: %s…%s", at[:8], at[-4:])

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
