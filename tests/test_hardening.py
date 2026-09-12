import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from server.memory_patcher import MemoryPatcher, rol32, ror32
import server.app as app


class TestCipherInversion(unittest.TestCase):
    def test_rol_ror_invertibility(self):
        test_values = [0, 1, 0xFFFFFFFF, 0x12345678, 0xDEADBEEF, 0x80000001, 0x55555555]
        for val in test_values:
            for r in range(1, 32):
                rotated = rol32(val, r)
                restored = ror32(rotated, r)
                self.assertEqual(val, restored, f"Failed invertibility for {hex(val)} at rot {r}")

    def test_game_currency_cipher_formula(self):
        # Test simulated pony currency encryption / decryption
        # formula: enc = rol32(xml_curr, 5) ^ c60
        # dec = ror32(c68 ^ c60, 5)
        c60 = 0xA1B2C3D4
        c64 = 0xE5F60718
        for target_curr in [1, 2, 3, 12]:
            val = rol32(target_curr, 5)
            c68 = c60 ^ val
            c6c = c64 ^ val

            dec = ror32(c68 ^ c60, 5)
            self.assertEqual(target_curr, dec)


class TestMemoryPatcherHardening(unittest.TestCase):
    def setUp(self):
        self.patcher = MemoryPatcher()

    def test_version_detection_strict_gating(self):
        # 1. Target version matches
        with patch.object(self.patcher, "_read_bytes", return_value=b"11.4.1a\x00"):
            res = self.patcher.detect_game_version(h_process=123, base_addr=0x140000000)
            self.assertTrue(res["matched"])
            self.assertIsNone(res["warning"])

        # 2. Canonical Windows package version matches
        with patch.object(self.patcher, "_read_bytes", return_value=b"11.4.0.0\x00"):
            res = self.patcher.detect_game_version(h_process=123, base_addr=0x140000000)
            self.assertTrue(res["matched"])
            self.assertIsNone(res["warning"])

        # 3. Future / different version must fail gating
        with patch.object(self.patcher, "_read_bytes", return_value=b"11.4.2\x00"):
            res = self.patcher.detect_game_version(h_process=123, base_addr=0x140000000)
            self.assertFalse(res["matched"])
            self.assertIn("Game client version mismatch", res["warning"])

        with patch.object(self.patcher, "_read_bytes", return_value=b"11.5.0a\x00"):
            res = self.patcher.detect_game_version(h_process=123, base_addr=0x140000000)
            self.assertFalse(res["matched"])

    def test_patch_memory_version_mismatch_aborts(self):
        # If version check fails, patch_memory must abort without modifying memory
        with patch.object(self.patcher, "find_process", return_value=9999), \
             patch("server.memory_patcher.OpenProcess", return_value=123), \
             patch("server.memory_patcher.CloseHandle", return_value=True), \
             patch.object(self.patcher, "get_main_module_base", return_value=0x140000000), \
             patch.object(self.patcher, "detect_game_version", return_value={"matched": False, "warning": "Version mismatch"}):

            res = self.patcher.patch_memory(allow_version_override=False)
            self.assertFalse(res["success"])
            self.assertIn("Patch aborted", res["message"])

    def test_patch_memory_signature_mismatch_aborts(self):
        # If any hook signature does not match orig or patch, must fail closed
        with patch.object(self.patcher, "find_process", return_value=9999), \
             patch("server.memory_patcher.OpenProcess", return_value=123), \
             patch("server.memory_patcher.CloseHandle", return_value=True), \
             patch.object(self.patcher, "get_main_module_base", return_value=0x140000000), \
             patch.object(self.patcher, "detect_game_version", return_value={"matched": True, "warning": None}), \
             patch.object(self.patcher, "_read_bytes", return_value=b"\xFF\xFF\xFF"):  # Corrupted bytes

            res = self.patcher.patch_memory()
            self.assertFalse(res["success"])
            self.assertIn("Signature mismatch", res["message"])

    def test_patch_memory_rollback_on_write_failure(self):
        # If writing a hook fails, automatic rollback must be triggered
        def mock_read(h, addr, length):
            # Return orig bytes for all hooks
            for info in self.patcher.PATCHES.values():
                if addr == 0x140000000 + info["rva"]:
                    return info["orig"]
            if addr == 0x140000000 + 0x6C9600:
                return self.patcher.VANILLA_ZONE_BYTES
            return b"\x00" * length

        with patch.object(self.patcher, "find_process", return_value=9999), \
             patch("server.memory_patcher.OpenProcess", return_value=123), \
             patch("server.memory_patcher.CloseHandle", return_value=True), \
             patch.object(self.patcher, "get_main_module_base", return_value=0x140000000), \
             patch.object(self.patcher, "detect_game_version", return_value={"matched": True, "warning": None}), \
             patch.object(self.patcher, "_read_bytes", side_effect=mock_read), \
             patch.object(self.patcher, "_write_bytes", return_value=False), \
             patch.object(self.patcher, "_rollback_transaction") as mock_rollback:

            res = self.patcher.patch_memory()
            self.assertFalse(res["success"])
            mock_rollback.assert_called_once()


class TestServerSecurityHardening(unittest.TestCase):
    def test_session_token_validation(self):
        # Create a mock request handler
        handler = app.StoreSuiteRequestHandler.__new__(app.StoreSuiteRequestHandler)
        handler.headers = {"X-Suite-Token": app.SESSION_TOKEN}
        self.assertTrue(handler._verify_token())

        handler.headers = {"X-Suite-Token": "invalid_token_12345"}
        self.assertFalse(handler._verify_token())

        handler.headers = {}
        self.assertFalse(handler._verify_token())

    def test_origin_validation_strict_localhost(self):
        handler = app.StoreSuiteRequestHandler.__new__(app.StoreSuiteRequestHandler)
        
        # Valid localhost headers
        handler.headers = {"Host": "127.0.0.1:8080", "Origin": "http://127.0.0.1:8080"}
        self.assertTrue(handler._is_allowed_origin())

        handler.headers = {"Host": "localhost:8080", "Origin": "http://localhost:8080"}
        self.assertTrue(handler._is_allowed_origin())

        # Malicious external origins must be rejected
        handler.headers = {"Host": "127.0.0.1:8080", "Origin": "http://evil-site.com"}
        self.assertFalse(handler._is_allowed_origin())

        handler.headers = {"Host": "malicious-domain.com", "Origin": "http://malicious-domain.com"}
        self.assertFalse(handler._is_allowed_origin())

    def test_path_traversal_detection(self):
        web_dir_resolved = app.WEB_DIR.resolve()

        traversal_paths = [
            web_dir_resolved.parent / "run.py",
            web_dir_resolved / ".." / "server" / "app.py",
            Path("C:/arbitrary_system_root/system_file.ini"),
            web_dir_resolved / ".hidden_file",
            web_dir_resolved / "assets_part1.zip",
        ]

        blocked_extensions = {".py", ".zip", ".7z"}

        for p in traversal_paths:
            resolved = p.resolve()
            try:
                is_safe = resolved.is_relative_to(web_dir_resolved)
            except AttributeError:
                is_safe = str(resolved).startswith(str(web_dir_resolved) + os.sep)
            
            try:
                is_common = os.path.commonpath([str(resolved), str(web_dir_resolved)]) == str(web_dir_resolved)
            except Exception:
                is_common = False

            has_blocked_ext = resolved.suffix.lower() in blocked_extensions
            is_hidden = any(part.startswith(".") for part in resolved.parts)

            is_prohibited = not (is_safe and is_common) or is_hidden or has_blocked_ext
            self.assertTrue(is_prohibited, f"Path traversal should be prohibited for: {p}")


if __name__ == "__main__":
    unittest.main()
