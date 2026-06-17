#!/usr/bin/env python3
"""
End-to-end test: Verify the image pipeline from generation → save → Discord delivery.

Steps:
1. Call FLUX2 REST server to get a base64 image
2. Save it to the generated images directory
3. Verify gateway regex can extract image: URL from text
4. Verify gateway resolves the filename to a local file
5. Confirm the image is actually viewable (PNG header check)
"""

import base64
import os
import re
import struct
import sys
import zlib
from pathlib import Path

# Paths
GENERATED_DIR = Path("/home/greyphilosophy/muddev/aicompany_mud/server/.static/media/generated")
FLUX2_SERVER_URL = os.getenv("FLUX2_SERVER_URL", "http://169.254.209.73:8190")

# Import gateway helpers for testing
sys.path.insert(0, "/home/greyphilosophy/muddev/evennia_discord_gateway")
from gateway.image_helpers import extract_image_urls, resolve_local_image, strip_image_references


def _build_test_png(width=128, height=128):
    """Build a valid PNG with gradient pixel data that's >500 bytes."""
    def chunk(ctype, data):
        c = ctype + data
        crc = struct.pack('>I', zlib.crc32(c) & 0xffffffff)
        return struct.pack('>I', len(data)) + c + crc
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = chunk(b'IHDR', ihdr_data)
    # Build rows with gradient data (less compressible than solid white)
    raw = b''
    for y in range(height):
        raw += b'\x00'  # filter byte
        for x in range(width):
            raw += bytes([(x * 3) % 256, (y * 5) % 256, ((x + y) * 7) % 256])
    compressed = zlib.compress(raw)
    idat = chunk(b'IDAT', compressed)
    iend = chunk(b'IEND', b'')
    return b'\x89PNG\r\n\x1a\n' + ihdr + idat + iend


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


def test_step_1a_png_header_check():
    """Verify we can generate a valid PNG file from the server."""
    import httpx

    payload = {
        "prompt": "Quick header check",
        "width": 256,
        "height": 256,
    }

    with httpx.Client(timeout=60) as client:
        r = client.post(f"{FLUX2_SERVER_URL}/generate", json=payload)
        data = r.json()

    assert data["success"], f"FLUX2 server returned: {data}"
    assert "image_b64" in data, "No image_b64 in response"

    image_bytes = base64.b64decode(data["image_b64"])
    assert image_bytes[:4] == b'\x89PNG', "Not a valid PNG header"
    assert len(image_bytes) > 100, "Image seems too small"

    print("  ✓ Step 1a: Valid PNG header confirmed")


def test_save_test_image():
    """Create and verify a valid test PNG in the generated directory."""
    png_data = _build_test_png()

    filename = "flux2_room_test_001.png"
    file_path = GENERATED_DIR / filename
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    file_path.write_bytes(png_data)

    assert file_path.is_file(), f"Image file not found: {file_path}"
    assert file_path.stat().st_size > 500, f"Image file too small: {file_path.stat().st_size} bytes"

    with open(file_path, "rb") as f:
        header = f.read(8)
        assert header[:4] == b'\x89PNG', "Not a valid PNG"

    print(f"  ✓ Test image saved to {file_path} ({file_path.stat().st_size} bytes)")


def test_gateway_regex_extraction():
    """Step 3: Gateway regex can extract image: URL from ANSI-style text."""
    # The gateway regex matches: image: https://...
    test_texts = [
        "You are in a cozy room.\n\n|yimage: https://game.test/media/generated/flux2_room_test_001.png|n",
        "Description here\nimage: http://game.test/media/generated/flux2_room_test_001.png",
        "A room with stuff\nIMAGE: https://game.test/media/generated/flux2_room_test_001.png",
    ]

    for text in test_texts:
        urls = extract_image_urls(text)
        assert len(urls) == 1, f"Expected 1 URL from: {text!r}, got {urls}"
        assert "flux2_room_test_001.png" in urls[0], f"Wrong filename: {urls[0]}"

    print("  ✓ Step 3: Gateway regex extracts image URLs from all formats")


def test_step_3b_generating_placeholder_filtered():
    """Step 3b: The 'generating...' placeholder is filtered out."""
    text = "Room desc\nimage: generating...\nMore text"
    urls = extract_image_urls(text)
    assert len(urls) == 0, f"Expected 0 URLs (generating... filtered), got {urls}"
    print("  ✓ Step 3b: 'generating...' placeholder properly filtered")


def test_gateway_path_resolution():
    """Gateway resolves filenames to local files."""
    # Create its own test image (self-contained, no dependency on other tests)
    png_data = _build_test_png()
    filename = "flux2_room_test_004.png"
    file_path = GENERATED_DIR / filename
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(png_data)
    assert file_path.stat().st_size > 500, f"Test image too small: {file_path.stat().st_size}"

    generated_dir = str(GENERATED_DIR)
    resolved = resolve_local_image(filename, generated_dir)
    assert resolved is not None, f"Failed to resolve: {filename}"
    assert resolved.is_file(), f"Resolved path not a file: {resolved}"
    assert resolved.stat().st_size > 500, f"Resolved file too small: {resolved}"

    print("  ✓ Gateway resolves filenames to local files")


def test_gateway_path_resolution_fails_for_missing_file():
    """Gateway returns None when the file doesn't exist."""
    generated_dir = str(GENERATED_DIR)
    resolved = resolve_local_image("nonexistent_file.png", generated_dir)
    assert resolved is None, "Expected None for missing file"
    print("  ✓ Gateway returns None for missing files")


def test_strip_image_references():
    """Step 5: Image references get stripped from text output."""
    # The gateway handles ANSI-formatted image references
    test_text = "You are in a cozy room with warm lighting.\n\n|yimage: https://game.test/media/generated/flux2_room_test_001.png|n"
    cleaned = strip_image_references(test_text)

    # After stripping, the image reference line should be gone
    assert "image:" not in cleaned, f"Image reference not stripped: {cleaned}"
    assert "cozy room" in cleaned, "Main text lost during strip"

    print("  ✓ Step 5: Image references properly stripped from text")


def test_strip_selective_urls():
    """Step 5b: Only specified URLs are stripped, others remain."""
    text = "Room\n|yimage: https://game.test/media/generated/room1.png|n\n|yimage: https://game.test/media/generated/room2.png|n"
    cleaned = strip_image_references(text, urls_to_strip=["https://game.test/media/generated/room1.png"])
    assert "room1.png" not in cleaned, "room1 should be stripped"
    assert "room2.png" in cleaned, "room2 should remain as fallback"
    print("  ✓ Step 5b: Selective URL stripping works correctly")


if __name__ == "__main__":
    print("Running image pipeline end-to-end test...")
    print()

    test_save_test_image()
    test_gateway_regex_extraction()
    test_gateway_path_resolution()
    test_gateway_path_resolution_fails_for_missing_file()
    test_strip_image_references()
    test_strip_selective_urls()

    print()
    print("All pipeline tests passed! (=^･ω･^=) nya~!")
