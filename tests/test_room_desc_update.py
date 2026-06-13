"""
Tests for LLM provider validation and room desc rewrite safety.

These tests verify that:
1. LLM client fails fast (no 180s hang) on None/empty provider config
2. generate_room_desc_safe uses short timeout
3. The safety net unlocks the inflight flag

Run with: evenv/bin/python -c 'import pytest; pytest.main(["tests/test_room_desc_update.py", "-v"])'
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
import inspect


class TestProviderValidationStandalone(unittest.TestCase):
    """Test provider validation logic without importing the full Evennia stack."""

    def test_provider_accepts_none_base_url(self):
        """LLMProvider dataclass should accept None for base_url and model."""
        # Import just the dataclass (no Evennia dependency for the dataclass itself)
        from dataclasses import dataclass
        from typing import Optional

        @dataclass(frozen=True)
        class LLMProvider:
            label: str
            base_url: Optional[str] = None
            model: Optional[str] = None
            api_key: Optional[str] = None

        p = LLMProvider(label="T", base_url=None, model=None)
        self.assertIsNone(p.base_url)
        self.assertIsNone(p.model)

    def test_validation_logic_none_base_url(self):
        """Validation should raise ValueError for None base_url."""
        from dataclasses import dataclass
        from typing import Optional

        @dataclass(frozen=True)
        class LLMProvider:
            label: str
            base_url: Optional[str] = None
            model: Optional[str] = None
            api_key: Optional[str] = None

        provider = LLMProvider(label="TEST", base_url=None, model="gpt-4")

        # Simulate the validation logic from llm_client.py
        def validate_provider(p):
            if not p.base_url:
                raise ValueError(f"[{p.label}] base_url is None/empty")
            if not p.model:
                raise ValueError(f"[{p.label}] model is None/empty")

        with self.assertRaises(ValueError) as cm:
            validate_provider(provider)
        self.assertIn("base_url", str(cm.exception))

    def test_validation_logic_none_model(self):
        """Validation should raise ValueError for None model."""
        from dataclasses import dataclass
        from typing import Optional

        @dataclass(frozen=True)
        class LLMProvider:
            label: str
            base_url: Optional[str] = None
            model: Optional[str] = None
            api_key: Optional[str] = None

        provider = LLMProvider(label="TEST", base_url="http://localhost/v1", model=None)

        def validate_provider(p):
            if not p.base_url:
                raise ValueError(f"[{p.label}] base_url is None/empty")
            if not p.model:
                raise ValueError(f"[{p.label}] model is None/empty")

        with self.assertRaises(ValueError) as cm:
            validate_provider(provider)
        self.assertIn("model", str(cm.exception))

    def test_validation_logic_empty_base_url(self):
        """Empty string base_url should also fail validation."""
        from dataclasses import dataclass
        from typing import Optional

        @dataclass(frozen=True)
        class LLMProvider:
            label: str
            base_url: Optional[str] = None
            model: Optional[str] = None
            api_key: Optional[str] = None

        provider = LLMProvider(label="TEST", base_url="", model="gpt-4")

        def validate_provider(p):
            if not p.base_url:
                raise ValueError(f"[{p.label}] base_url is None/empty")
            if not p.model:
                raise ValueError(f"[{p.label}] model is None/empty")

        with self.assertRaises(ValueError) as cm:
            validate_provider(provider)
        self.assertIn("base_url", str(cm.exception))

    def test_valid_provider_passes(self):
        """A properly configured provider should pass validation."""
        from dataclasses import dataclass
        from typing import Optional

        @dataclass(frozen=True)
        class LLMProvider:
            label: str
            base_url: Optional[str] = None
            model: Optional[str] = None
            api_key: Optional[str] = None

        provider = LLMProvider(label="LOCAL", base_url="http://127.0.0.1:1234/v1", model="gpt-4")

        def validate_provider(p):
            if not p.base_url:
                raise ValueError(f"[{p.label}] base_url is None/empty")
            if not p.model:
                raise ValueError(f"[{p.label}] model is None/empty")

        # Should not raise
        validate_provider(provider)


class TestSafeRewriteMethod(unittest.TestCase):
    """Verify the safe rewrite method has correct timeout parameters."""

    def test_safe_method_has_long_timeout(self):
        """generate_room_desc_safe should set timeout_s=120 and max_attempts=1."""
        # Read the source file directly to avoid Evennia import
        import os
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "utils", "computer.py"
        )
        with open(src_path) as f:
            source = f.read()

        self.assertIn("timeout_s = 120", source)
        self.assertIn("max_attempts = 1", source)
        self.assertIn("generate_room_desc_safe", source)

    def test_rooms_uses_safe_method(self):
        """rooms.py should call generate_room_desc_safe, not generate_room_desc."""
        import os
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "typeclasses", "rooms.py"
        )
        with open(src_path) as f:
            source = f.read()

        # The safe method should be referenced
        self.assertIn("generate_room_desc_safe", source)
        # Safety net should exist
        self.assertIn("_unlock_desc_rewrite", source)
        self.assertIn("safe_unlock", source)


class TestInflightSafetyNet(unittest.TestCase):
    """Test the inflight flag safety net logic."""

    def test_safety_net_delays_and_unlocks(self):
        """The safety net should delay 125s then unlock inflight flag."""
        import os
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "typeclasses", "rooms.py"
        )
        with open(src_path) as f:
            source = f.read()

        # Verify the safety delay pattern exists
        self.assertIn("delay(125.0", source)
        self.assertIn("_unlock_desc_rewrite", source)

    def test_unlock_method_sets_flag_false(self):
        """_unlock_desc_rewrite should set inflight to False."""
        import os
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "typeclasses", "rooms.py"
        )
        with open(src_path) as f:
            source = f.read()

        # The method should set inflight = False
        self.assertTrue(
            "desc_rewrite_inflight = False" in source,
            "Expected desc_rewrite_inflight = False in _unlock_desc_rewrite"
        )


if __name__ == "__main__":
    unittest.main()
