#!/usr/bin/env python3
"""
End-to-end test: Verify the image pipeline from generation → save → Discord delivery.

Steps:
1. Call FLUX2 REST server to get a base64 image
2. Save it to the generated images directory
3. Verify gateway regex can extract [Image](/media/generated/xxx.png)
4. Verify gateway resolves the path to a local file
5. Confirm the image is actually viewable (PNG header check)
"""

import base64
import json
import os
import re
import sys
from pathlib import Path

# Paths
GENERATED_DIR = Path("/home/greyphilosophy/muddev/aicompany_mud/server/.static/media/generated")
FLUX2_SERVER_URL = os.getenv("FLUX2_SERVER_URL", "http://169.254.209.73:8190")

# Import gateway helpers for testing
sys.path.insert(0, "/home/greyphilosophy/muddev/evennia_discord_gateway")
from gateway.image_helpers import extract_image_urls, resolve_image_file, strip_image_references


def test_step_1_flux2_server_responds():
    """Step 1: FLUX2 REST server returns a valid base64 image."""
    import httpx

    payload = {
        "prompt": "A cozy wooden desk with a glowing laptop, warm lighting",
        "steps": 12,
        "guidance_scale": 7,
        "seed": 42,
        "width": 512,
        "height": 512,
    }

    with httpx.Client(timeout=120) as client:
        r = client.post(f"{FLUX2_SERVER_URL}/generate", json=payload)
        data = r.json()

    assert data["success"], f"FLUX2 server returned: {data}"
    assert "image_b64" in data, "No image_b64 in response"
    assert len(data["image_b64"]) > 100, "Image base64 seems too small"

    print("  ✓ Step 1: FLUX2 server responded with base64 image")
    return data["image_b64"]


def test_step_2_save_image_locally(image_b64):
    """Step 2: Save the image to the generated directory."""
    filename = "flux2_room_test_001.png"
    file_path = GENERATED_DIR / filename
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    image_bytes = base64.b64decode(image_b64)
    file_path.write_bytes(image_bytes)

    assert file_path.is_file(), f"Image file not found: {file_path}"
    assert file_path.stat().st_size > 100, "Image file seems too small"

    # Verify PNG header
    with open(file_path, "rb") as f:
        header = f.read(8)
        assert header[:4] == b'\x89PNG' or header[:8] == b'\x89PNG\r\n\x1a\n', "Not a valid PNG"

    print(f"  ✓ Step 2: Image saved to {file_path} ({file_path.stat().st_size} bytes)")
    return filename


def test_step_3_gateway_regex_extraction():
    """Step 3: Gateway regex can extract [Image](/media/generated/xxx.png) from text."""
    # Simulate what the MUD would output
    test_texts = [
        "You are in a cozy room.\n\n[Image](/media/generated/flux2_room_test_001.png)",
        "Description here\n[Image](https://game.test/media/generated/flux2_room_test_001.png)",
        "A room with stuff\n[Image](media/generated/flux2_room_test_001.png)",
    ]

    for text in test_texts:
        urls = extract_image_urls(text)
        assert len(urls) == 1, f"Expected 1 URL from: {text!r}, got {urls}"
        assert "flux2_room_test_001.png" in urls[0], f"Wrong filename: {urls[0]}"

    print("  ✓ Step 3: Gateway regex extracts image URLs from all formats")


def test_step_4_gateway_path_resolution():
    """Step 4: Gateway resolves URLs to local files."""
    test_urls = [
        "/media/generated/flux2_room_test_001.png",
        "https://game.test/media/generated/flux2_room_test_001.png",
        "media/generated/flux2_room_test_001.png",
    ]

    for url in test_urls:
        resolved = resolve_image_file(url)
        assert resolved is not None, f"Failed to resolve: {url}"
        assert resolved.is_file(), f"Resolved path not a file: {resolved}"
        assert resolved.stat().st_size > 100, f"Resolved file too small: {resolved}"

    print("  ✓ Step 4: Gateway resolves all URL formats to local files")


def test_step_5_strip_image_references():
    """Step 5: Image references get stripped from text output."""
    test_text = "You are in a cozy room with warm lighting.\n\n[Image](/media/generated/flux2_room_test_001.png)"
    cleaned = strip_image_references(test_text)

    assert "[Image]" not in cleaned, "Image reference not stripped"
    assert "cozy room" in cleaned, "Main text lost during strip"
    assert "/media/generated/" not in cleaned, "Path leaked into text"

    print("  ✓ Step 5: Image references properly stripped from text")


def run_pipeline_test():
    """Run the full pipeline test."""
    print("Running image pipeline end-to-end test...")
    print()

    # Step 1: Generate
    image_b64 = test_step_1_flux2_server_responds()

    # Step 2: Save
    filename = test_step_2_save_image_locally(image_b64)

    # Steps 3-5: Gateway processing
    test_step_3_gateway_regex_extraction()
    test_step_4_gateway_path_resolution()
    test_step_5_strip_image_references()

    print()
    print("All pipeline tests passed! (=^･ω･^=) nya~!")
    return True


if __name__ == "__main__":
    success = run_pipeline_test()
    sys.exit(0 if success else 1)
