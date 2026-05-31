#!/usr/bin/env python3
"""
Lightweight OpenAI-compatible API server for Qwen3-14B-NVFP4.
Uses direct PyTorch + Transformers loading to avoid vLLM container overhead.
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

# ── Model loading ──────────────────────────────────────────────────

MODEL_DIR = "/home/greyphilosophy/models/qwen3-14b-nvfp4"
DEVICE = "cuda:0"
MAX_NEW_TOKENS = 2048
TEMPERATURE = 0.7
TOP_P = 0.9
MAX_HISTORY_TOKENS = 4096

print(f"[mud-llm] Loading model from {MODEL_DIR} ...", flush=True)

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR,
    trust_remote_code=True,
    device_map=DEVICE,
    torch_dtype=torch.bfloat16,
)
model.eval()

# Get VRAM usage
allocated = torch.cuda.memory_allocated(DEVICE)
reserved = torch.cuda.memory_reserved(DEVICE)
print(
    f"[mud-llm] Loaded. Allocated: {allocated/1e9:.1f}GB, Reserved: {reserved/1e9:.1f}GB",
    flush=True,
)


# ── Request / Response models ──────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "Qwen3-14B-NVFP4"
    messages: List[Message]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    max_tokens: Optional[int] = 2048
    stream: bool = False


class Choice(BaseModel):
    message: Message
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str = "chatcmpl-mud-llm"
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
    id: str = "chatcmpl-mud-llm"
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[StreamChoice]


# ── Inference ──────────────────────────────────────────────────────

def build_prompt(messages: List[Message]) -> str:
    """Build prompt using the chat template."""
    chat_msgs = [{"role": m.role, "content": m.content} for m in messages]
    return tokenizer.apply_chat_template(chat_msgs, tokenize=False, add_generation_cfg=True)


def generate(messages: List[Message], temperature: float, top_p: float, max_tokens: int):
    """Synchronous generation."""
    prompt = build_prompt(messages)
    inputs = tokenizer(prompt, return_tensors="pt").to(DEVICE)
    prompt_len = inputs["input_ids"].shape[1]

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature if temperature > 0 else None,
            top_p=top_p if top_p < 1.0 else None,
            do_sample=temperature > 0,
        )

    # Decode only the new tokens
    generated = output[0][prompt_len:]
    text = tokenizer.decode(generated, skip_special_tokens=True)
    return text, prompt_len, output[0].shape[0]


# ── Streaming generation ─────────────────────────────────────────

class StreamGenerator:
    """Generator that yields tokens as they arrive."""

    def __init__(self, messages, temperature, top_p, max_tokens):
        self.messages = messages
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens

    def generate(self):
        prompt = build_prompt(self.messages)
        inputs = tokenizer(prompt, return_tensors="pt").to(DEVICE)
        prompt_len = inputs["input_ids"].shape[1]

        with torch.no_grad():
            # Use model's generate with a streaming approach
            from transformers import TextIteratorStreamer
            streamer = TextIteratorStreamer(
                tokenizer, skip_special_tokens=True, timeout=5
            )

            gen_kwargs = dict(
                **inputs,
                max_new_tokens=self.max_tokens,
                temperature=self.temperature if self.temperature > 0 else None,
                top_p=self.top_p if self.top_p < 1.0 else None,
                do_sample=self.temperature > 0,
                streamer=streamer,
            )

            gen_thread = threading.Thread(target=model.generate, kwargs=gen_kwargs)
            gen_thread.start()

            for new_text in streamer:
                yield new_text

            gen_thread.join()


# ── FastAPI app ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[mud-llm] Server ready", flush=True)
    yield

app = FastAPI(title="MUD LLM", version="1.0.0", lifespan=lifespan)


@app.get("/v1/models")
async def list_models():
    return {
        "data": [
            {
                "id": "Qwen3-14B-NVFP4",
                "object": "model",
                "owned_by": "nvidia",
                "context_length": 32768,
            }
        ]
    }


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    if len(req.messages) == 0:
        raise HTTPException(400, "messages is required")

    if req.stream:
        gen = StreamGenerator(
            req.messages, req.temperature or 0.7, req.top_p or 0.9,
            req.max_tokens or MAX_NEW_TOKENS,
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
        req.messages, req.temperature or 0.7, req.top_p or 0.9,
        req.max_tokens or MAX_NEW_TOKENS,
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
    PORT = int(os.environ.get("MUD_LLM_PORT", "30001"))
    HOST = os.environ.get("MUD_LLM_HOST", "127.0.0.1")

    uvicorn.run(
        "mud_llm_server:app",
        host=HOST,
        port=PORT,
        workers=1,
        log_level="info",
    )
