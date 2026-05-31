#!/usr/bin/env python3
"""
Lightweight OpenAI-compatible API server for local LLM inference.
Uses direct PyTorch + Transformers loading to avoid vLLM container overhead.

Configure via environment variables:
  MUD_LLM_MODEL_DIR — Path to the model directory (required)
  MUD_LLM_PORT      — Listen port (default: 30001)
  MUD_LLM_HOST      — Bind address (default: 127.0.0.1)
  MUD_LLM_MAX_NEW_TOKENS    — Max tokens per completion (default: 2048)
  MUD_LLM_TEMPERATURE      — Sampling temperature (default: 0.7)
  MUD_LLM_TOP_P            — Top-p sampling (default: 0.9)
  MUD_LLM_MAX_HISTORY     — Max history tokens (default: 32768)
  MUD_LLM_CONTEXT_LENGTH   — Context length for /v1/models (default: 32768)
"""

import json
import os
import sys
import time
import threading
from contextlib import asynccontextmanager
from typing import List, Optional

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import uvicorn


def get_config():
    """Read configuration from environment variables."""
    model_dir = os.environ.get("MUD_LLM_MODEL_DIR")
    if not model_dir:
        # Try settings.py as fallback
        try:
            import os.path
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            settings_path = os.path.join(project_root, "server", "conf", "secret_settings.py")
            if os.path.exists(settings_path):
                # Minimal import without Django
                ns = {}
                with open(settings_path) as f:
                    exec(f.read(), ns)
                if "LLM_SERVER_MODEL_DIR" in ns:
                    model_dir = ns["LLM_SERVER_MODEL_DIR"]
        except Exception:
            pass

    return {
        "model_dir": model_dir,
        "port": int(os.environ.get("MUD_LLM_PORT", "30001")),
        "host": os.environ.get("MUD_LLM_HOST", "127.0.0.1"),
        "max_new_tokens": int(os.environ.get("MUD_LLM_MAX_NEW_TOKENS", "2048")),
        "temperature": float(os.environ.get("MUD_LLM_TEMPERATURE", "0.7")),
        "top_p": float(os.environ.get("MUD_LLM_TOP_P", "0.9")),
        "max_history_tokens": int(os.environ.get("MUD_LLM_MAX_HISTORY", "32768")),
        "context_length": int(os.environ.get("MUD_LLM_CONTEXT_LENGTH", "32768")),
    }


# ── Request / Response models ──────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "local-llm"
    messages: List[Message]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    max_tokens: Optional[int] = 2048
    stream: bool = False


class Choice(BaseModel):
    message: Message
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str = "chatcmpl-local"
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Optional[dict] = None


class DeltaMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = ""


class StreamChoice(BaseModel):
    index: int = 0
    delta: DeltaMessage
    finish_reason: Optional[str] = "stop"


class StreamResponse(BaseModel):
    id: str = "chatcmpl-local"
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[StreamChoice]


# ── Global model state (loaded async) ────────────────────────────

_model: Optional[Any] = None
_tokenizer: Optional[Any] = None
_device: str = "cuda:0"
_model_ready: bool = False
_config = None


def _load_model(model_dir: str):
    """Load the model and tokenizer. Called during FastAPI lifespan."""
    global _model, _tokenizer, _model_ready, _device

    if not torch.cuda.is_available():
        _device = "cpu"

    print(f"[mud-llm] Loading model from {model_dir} ...", flush=True)

    _tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
    _model = AutoModelForCausalLM.from_pretrained(
        model_dir,
        trust_remote_code=True,
        device_map=_device,
        torch_dtype=torch.bfloat16,
    )
    _model.eval()

    allocated = torch.cuda.memory_allocated(_device) if torch.cuda.is_available() else 0
    reserved = torch.cuda.memory_reserved(_device) if torch.cuda.is_available() else 0
    print(
        f"[mud-llm] Loaded. Allocated: {allocated/1e9:.1f}GB, Reserved: {reserved/1e9:.1f}GB",
        flush=True,
    )
    _model_ready = True


# ── Inference ─────────────────────────────────────────────────────

def build_prompt(messages: List[Message]) -> str:
    """Build prompt using the chat template."""
    if _tokenizer is None:
        raise RuntimeError("Tokenizer not loaded")
    chat_msgs = [{"role": m.role, "content": m.content} for m in messages]
    return _tokenizer.apply_chat_template(chat_msgs, tokenize=False, add_generation_cfg=True)


def generate(messages: List[Message], temperature: float, top_p: float, max_tokens: int, context_length: int):
    """Synchronous generation."""
    if _model is None or _tokenizer is None:
        raise RuntimeError("Model not loaded")

    prompt = build_prompt(messages)
    inputs = _tokenizer(prompt, return_tensors="pt").to(_device)
    prompt_len = inputs["input_ids"].shape[1]

    with torch.no_grad():
        output = _model.generate(
            **inputs,
            max_new_tokens=min(max_tokens, context_length),
            temperature=temperature if temperature > 0 else None,
            top_p=top_p if top_p < 1.0 else None,
            do_sample=temperature > 0,
        )

    generated = output[0][prompt_len:]
    text = _tokenizer.decode(generated, skip_special_tokens=True)
    return text, prompt_len, output[0].shape[0]


class StreamGenerator:
    """Generator that yields tokens as they arrive."""

    def __init__(self, messages, temperature, top_p, max_tokens, context_length):
        self.messages = messages
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = min(max_tokens, context_length)

    def generate(self):
        if _model is None or _tokenizer is None:
            raise RuntimeError("Model not loaded")

        prompt = build_prompt(self.messages)
        inputs = _tokenizer(prompt, return_tensors="pt").to(_device)

        from transformers import TextIteratorStreamer
        streamer = TextIteratorStreamer(
            _tokenizer, skip_special_tokens=True, timeout=5
        )

        gen_kwargs = dict(
            **inputs,
            max_new_tokens=self.max_tokens,
            temperature=self.temperature if self.temperature > 0 else None,
            top_p=self.top_p if self.top_p < 1.0 else None,
            do_sample=self.temperature > 0,
            streamer=streamer,
        )

        gen_thread = threading.Thread(target=_model.generate, kwargs=gen_kwargs)
        gen_thread.start()

        for new_text in streamer:
            yield new_text

        gen_thread.join()


# ── FastAPI app ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model_ready, _config
    config = get_config()
    _config = config

    if config["model_dir"] is None:
        print("[mud-llm] WARNING: MUD_LLM_MODEL_DIR not set — loading deferred to first request")
    else:
        _load_model(config["model_dir"])
    print("[mud-llm] Server ready", flush=True)
    yield

app = FastAPI(title="MUD LLM", version="1.0.0", lifespan=lifespan)


@app.get("/v1/models")
async def list_models():
    model_dir = _config["model_dir"] if _config else None
    context_length = _config["context_length"] if _config else 32768
    return {
        "data": [
            {
                "id": model_dir.split("/")[-1] if model_dir else "local-llm",
                "object": "model",
                "owned_by": "local",
                "context_length": context_length,
            }
        ]
    }


@app.get("/health")
async def health_check():
    return {"status": "ready" if _model_ready else "loading", "model_ready": _model_ready}


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    if _config is None:
        raise HTTPException(503, "Configuration not loaded")

    if not _model_ready:
        raise HTTPException(503, "Model still loading")

    if len(req.messages) == 0:
        raise HTTPException(400, "messages is required")

    max_new_tokens = _config["max_new_tokens"] if _config else 2048

    if req.stream:
        gen = StreamGenerator(
            req.messages,
            req.temperature or 0.7,
            req.top_p or 0.9,
            req.max_tokens or max_new_tokens,
            _config["max_history_tokens"],
        )

        async def stream_iter():
            ts = int(time.time())
            for token_text in gen.generate():
                chunk = StreamResponse(
                    created=ts,
                    choices=[StreamChoice(delta=DeltaMessage(content=token_text))],
                )
                yield f"data: {chunk.model_dump_json()}\n\n"
            yield 'data: {"choices": [{"delta": {}, "finish_reason": "stop"}]}\n\n'
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_iter(), media_type="text/event-stream")

    # Non-streaming
    text, prompt_tokens, total_tokens = generate(
        req.messages,
        req.temperature or 0.7,
        req.top_p or 0.9,
        req.max_tokens or max_new_tokens,
        _config["max_history_tokens"],
    )

    return ChatCompletionResponse(
        created=int(time.time()),
        choices=[
            Choice(
                message=Message(role="assistant", content=text),
                finish_reason="stop",
            )
        ],
        usage={
            "prompt_tokens": prompt_tokens,
            "total_tokens": total_tokens,
            "completion_tokens": total_tokens - prompt_tokens,
        },
    )


# ── Entry point ──────────────────────────────────────────────────

if __name__ == "__main__":
    config = get_config()
    uvicorn.run(
        "mud_llm_server:app",
        host=config["host"],
        port=config["port"],
        workers=1,
        log_level="info",
    )
