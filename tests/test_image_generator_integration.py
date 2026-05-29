"""
Integration tests for the ComfyUI job queue system.

Tests verify that:
- Jobs can be submitted via the queue with round-trip tracking
- Subject-level deduplication works
- Depth limiting (max_pending) works
- Await completions returns results with correct metadata

Requires: evennia-ai-image-generator installed, ComfyUI on port 8188.
Skipped automatically if the package is missing.
"""
import importlib.util

import httpx
import pytest

if not importlib.util.find_spec("evennia_ai_image_generator"):
    pytest.skip(
        "evennia_ai_image_generator not installed", allow_module_level=True
    )

# Imports gated by the skip above — if we're here, the package is installed.
from evennia_ai_image_generator.backend.base import ImageGenerationRequest
from evennia_ai_image_generator.backend.comfyui_backend import ComfyUIBackend
from evennia_ai_image_generator.backend.comfyui_queue import (
    ComfyUIQueue,
    JobInfo,
    QueueAction,
)

# ComfyUI should be running on port 8188
COMFYUI_SERVER = "http://127.0.0.1:8188"


@pytest.fixture
def comfyui_backend():
    """Return a ComfyUI backend with dry_run=False (live server)."""
    backend = ComfyUIBackend(
        server_url=COMFYUI_SERVER,
        scheduler="karras",
        sampler_name="euler",
        default_steps=10,
        default_cfg=7.5,
        output_dir="generated",
        media_url_base="http://127.0.0.1:8188/output",
        timeout_s=120.0,
        max_wait_s=600.0,
    )
    # Pre-resolve checkpoint so tests don't hit the API repeatedly
    backend._checkpoint_cache = backend._resolve_checkpoint()
    return backend


def test_queue_submits_and_tracks_job(comfyui_backend):
    """Submit a single job via the queue and verify round-trip tracking."""
    queue = ComfyUIQueue(max_pending=5)
    request = ImageGenerationRequest(
        subject_type="object",
        subject_key="queue_test_1",
        prompt="A red crystal on a pedestal",
        negative_prompt="blurry",
        mode="txt2img",
        seed=100,
        width=512,
        height=512,
    )

    action = queue.enqueue(request, comfyui_backend)
    assert action == "submitted"
    assert queue.pending_count() == 1

    # Verify we can track the job
    job = queue.get_job("queue_test_1")
    assert job is not None
    assert job.status == "submitted"
    assert job.job_id is not None
    assert job.prompt_id is not None


def test_queue_deduplicates_by_subject_key(comfyui_backend):
    """Two requests with the same subject_key should deduplicate."""
    queue = ComfyUIQueue(max_pending=5)
    request = ImageGenerationRequest(
        subject_type="object",
        subject_key="queue_dedup",
        prompt="A blue gem",
        negative_prompt="blurry",
        mode="txt2img",
        seed=200,
        width=512,
        height=512,
    )

    action1 = queue.enqueue(request, comfyui_backend)
    assert action1 == "submitted"

    # Second request with same key
    request2 = ImageGenerationRequest(
        subject_type="object",
        subject_key="queue_dedup",
        prompt="Another blue gem",
        negative_prompt="blurry",
        mode="txt2img",
        seed=201,
        width=512,
        height=512,
    )
    action2 = queue.enqueue(request2, comfyui_backend)
    assert action2 == "duplicate"
    assert queue.pending_count() == 1


def test_queue_enforces_max_pending(comfyui_backend):
    """When max_pending is reached, new jobs should be marked as full."""
    # Small queue
    queue = ComfyUIQueue(max_pending=1)

    request1 = ImageGenerationRequest(
        subject_type="object",
        subject_key="cap_test_a",
        prompt="A yellow orb",
        negative_prompt="blurry",
        mode="txt2img",
        seed=300,
        width=512,
        height=512,
    )
    action1 = queue.enqueue(request1, comfyui_backend)
    assert action1 == "submitted"

    # Queue is full now
    request2 = ImageGenerationRequest(
        subject_type="object",
        subject_key="cap_test_b",
        prompt="A green orb",
        negative_prompt="blurry",
        mode="txt2img",
        seed=301,
        width=512,
        height=512,
    )
    action2 = queue.enqueue(request2, comfyui_backend)
    assert action2 == "full"


def test_queue_await_completions_returns_results(comfyui_backend):
    """Submit a job, await completions, and verify the result."""
    queue = ComfyUIQueue(max_pending=5)
    request = ImageGenerationRequest(
        subject_type="object",
        subject_key="queue_await_test",
        prompt="A purple gem on a velvet pillow",
        negative_prompt="blurry",
        mode="txt2img",
        seed=400,
        width=512,
        height=512,
    )

    action = queue.enqueue(request, comfyui_backend)
    assert action == "submitted"

    # Wait for completions with a reasonable timeout
    results = queue.await_completions(
        comfyui_backend,
        timeout_s=300.0,
        poll_interval=0.5,
    )

    assert len(results) == 1
    job = results[0]
    assert job.status == "complete"
    assert job.result is not None
    assert job.result.image_path is not None
    assert job.result.image_url is not None
    # Verify round-trip metadata
    assert "job_id" in job.result.metadata
    assert "prompt_id" in job.result.metadata
    assert job.result.metadata["job_id"] == job.job_id
    assert job.result.metadata["prompt_id"] == job.prompt_id


def test_queue_cancel_works(comfyui_backend):
    """Cancel should remove a job from the active set."""
    queue = ComfyUIQueue(max_pending=5)
    request = ImageGenerationRequest(
        subject_type="object",
        subject_key="queue_cancel_test",
        prompt="An orange crystal",
        negative_prompt="blurry",
        mode="txt2img",
        seed=500,
        width=512,
        height=512,
    )

    action = queue.enqueue(request, comfyui_backend)
    assert action == "submitted"
    assert queue.pending_count() == 1

    # Cancel it
    cancelled = queue.cancel("queue_cancel_test")
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert queue.pending_count() == 0


def test_queue_multiple_concurrent_jobs(comfyui_backend):
    """Submit multiple jobs and verify they all complete."""
    queue = ComfyUIQueue(max_pending=3)

    for i in range(3):
        request = ImageGenerationRequest(
            subject_type="object",
            subject_key=f"multi_job_{i}",
            prompt=f"A colored crystal #{i}",
            negative_prompt="blurry",
            mode="txt2img",
            seed=600 + i,
            width=512,
            height=512,
        )
        action = queue.enqueue(request, comfyui_backend)
        assert action == "submitted"

    assert queue.pending_count() == 3
    assert set(queue.pending_keys()) == {"multi_job_0", "multi_job_1", "multi_job_2"}

    # Wait for all
    results = queue.await_completions(
        comfyui_backend,
        timeout_s=600.0,
        poll_interval=0.5,
    )

    assert len(results) == 3
    for job in results:
        assert job.status == "complete"
        assert job.result is not None


def test_queue_job_ids_are_round_trip_trackable(comfyui_backend):
    """Verify that job_id flows through ComfyUI and back via history."""
    queue = ComfyUIQueue(max_pending=2)
    request = ImageGenerationRequest(
        subject_type="object",
        subject_key="roundtrip_test",
        prompt="A diamond ring",
        negative_prompt="blurry",
        mode="txt2img",
        seed=700,
        width=512,
        height=512,
    )

    action = queue.enqueue(request, comfyui_backend)
    job = queue.get_job("roundtrip_test")
    assert job is not None

    # Check ComfyUI history directly — the prompt_id is our round-trip key
    results = queue.await_completions(
        comfyui_backend,
        timeout_s=300.0,
        poll_interval=0.5,
    )

    assert len(results) == 1
    result = results[0]
    assert result.result is not None
    # Verify that prompt_id matches what's stored
    assert result.result.metadata["prompt_id"] == result.prompt_id
    assert result.result.metadata["job_id"] == result.job_id
