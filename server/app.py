import os
import sys
import json
import secrets
import mimetypes
from typing import Any
from pathlib import Path
try:
    from http.server import ThreadingHTTPServer as DefaultHTTPServer
except ImportError:
    from http.server import HTTPServer as DefaultHTTPServer
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from server.memory_patcher import MemoryPatcher

mem_patcher = MemoryPatcher()
mem_patcher.set_auto_watch(True)

WEB_DIR = PROJECT_DIR / "web"

# Transient per-launch security token for API authentication and CSRF prevention
SESSION_TOKEN = secrets.token_hex(16)


def ensure_assets(project_dir: Path = PROJECT_DIR) -> bool:
    """
    Checks if web/assets/portraits contains portrait images.
    If empty or void of image files, automatically extracts from
    web/assets_part*.zip (multi-part archives under GitHub's 25MB limit) or web/assets.zip.
    Includes strict Zip Slip validation: prohibits traversal patterns and non-PNG members.
    """
    web_dir = project_dir / "web"
    portraits_dir = web_dir / "assets" / "portraits"

    if portraits_dir.is_dir():
        png_count = sum(1 for _ in portraits_dir.glob("*.png"))
        if png_count >= 100:
            return True

    # Check for split archives (assets_part1.zip, assets_part2.zip, ...) or single assets.zip
    zip_files = []
    part_zips = sorted(web_dir.glob("assets_part*.zip"))
    if part_zips:
        zip_files.extend(part_zips)
    else:
        for candidate in [web_dir / "assets.zip", project_dir / "data" / "assets.zip", project_dir / "assets.zip"]:
            if candidate.is_file():
                zip_files.append(candidate)
                break

    if not zip_files:
        return False

    names_str = ", ".join(z.name for z in zip_files)
    print(f"[ASSETS] Catalog portrait directory is empty. Unpacking from {names_str}...")
    try:
        import zipfile
        portraits_dir.mkdir(parents=True, exist_ok=True)
        for z_path in zip_files:
            with zipfile.ZipFile(z_path, "r") as zf:
                for member in zf.infolist():
                    # 1. Reject paths with directory traversal or absolute roots
                    norm_name = os.path.normpath(member.filename)
                    if (
                        norm_name.startswith("..")
                        or os.path.isabs(norm_name)
                        or member.filename.startswith("/")
                        or member.filename.startswith("\\")
                    ):
                        raise RuntimeError(f"Zip Slip traversal blocked for entry: {member.filename}")

                    # 2. Only allow .png portrait image extraction
                    if not member.filename.lower().endswith(".png"):
                        continue

                    if member.filename.startswith("portraits/"):
                        dest_dir = web_dir / "assets"
                    elif member.filename.startswith("assets/"):
                        dest_dir = web_dir
                    else:
                        dest_dir = portraits_dir

                    # 3. Ensure extracted path resides strictly inside dest_dir
                    dest_resolved = dest_dir.resolve()
                    target_path = (dest_dir / member.filename).resolve()
                    try:
                        is_safe = target_path.is_relative_to(dest_resolved)
                    except AttributeError:
                        is_safe = str(target_path).startswith(str(dest_resolved) + os.sep)

                    if not is_safe:
                        raise RuntimeError(f"Zip Slip traversal blocked for entry: {member.filename}")
                    zf.extract(member, dest_dir)
        extracted_count = sum(1 for _ in portraits_dir.glob("*.png"))
        print(f"[ASSETS] Extraction complete: {extracted_count} portraits unpacked to {portraits_dir.name}/.")
        return True
    except Exception as e:
        print(f"[ASSETS] Error extracting assets archive: {e}")
        return False


# Automatically verify/extract assets on startup
ensure_assets(PROJECT_DIR)


class RobustThreadingHTTPServer(DefaultHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        exc_type, _, _ = sys.exc_info()
        if exc_type in (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            return
        mem_patcher.log("ERROR", f"Server worker exception: {sys.exc_info()[1]}")


class StoreSuiteRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Keep server console clean; internal logs go through mem_patcher
        pass

    def _is_allowed_origin(self) -> bool:
        """Validates that request Host and Origin headers point strictly to localhost."""
        host = self.headers.get("Host", "").split(":")[0]
        if host and host not in ("127.0.0.1", "localhost"):
            return False

        origin = self.headers.get("Origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.hostname not in ("127.0.0.1", "localhost"):
                return False
        return True

    def _verify_token(self) -> bool:
        """Validates that incoming state-changing request contains valid X-Suite-Token header."""
        token = self.headers.get("X-Suite-Token")
        return bool(token and secrets.compare_digest(token, SESSION_TOKEN))

    def _send_json(self, data: Any, status: int = 200):
        try:
            body = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            origin = self.headers.get("Origin")
            if origin and self._is_allowed_origin():
                self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception as ex:
            mem_patcher.log("ERROR", f"_send_json exception: {ex}")

    def _read_json_body(self) -> dict:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                raw_body = self.rfile.read(content_length).decode("utf-8", errors="replace")
                return json.loads(raw_body)
        except Exception as ex:
            mem_patcher.log("WARN", f"Failed to parse JSON body: {ex}")
        return {}

    def do_OPTIONS(self):
        try:
            if not self._is_allowed_origin():
                self.send_error(403, "Cross-Origin Access Forbidden")
                return
            self.send_response(200)
            origin = self.headers.get("Origin", "http://127.0.0.1:8080")
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Suite-Token, X-MLP-Request")
            self.end_headers()
        except Exception as ex:
            mem_patcher.log("ERROR", f"do_OPTIONS exception: {ex}")

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/api/status":
                self._send_json(mem_patcher.get_status())
                return

            elif path == "/api/catalog":
                self._send_json(mem_patcher.get_shop_catalog())
                return

            elif path == "/api/logs":
                self._send_json(mem_patcher.get_logs())
                return

            # Static Web files
            if path == "/" or path == "" or path == "/index.html":
                file_to_serve = (WEB_DIR / "index.html").resolve()
                if file_to_serve.is_file():
                    with open(file_to_serve, "r", encoding="utf-8") as f:
                        html_content = f.read()
                    # Inject transient session token into HTML for the WebGUI
                    html_content = html_content.replace("{{SUITE_TOKEN}}", SESSION_TOKEN)
                    body = html_content.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                else:
                    self.send_error(404, "index.html not found")
                    return

            rel = path.lstrip("/")
            file_to_serve = (WEB_DIR / rel).resolve()
            web_dir_resolved = WEB_DIR.resolve()

            # Path Traversal Prevention: Ensure target file resides strictly inside WEB_DIR
            try:
                is_safe = file_to_serve.is_relative_to(web_dir_resolved)
            except AttributeError:
                is_safe = str(file_to_serve).startswith(str(web_dir_resolved) + os.sep)

            # Commonpath defense against separator manipulation
            try:
                is_common = os.path.commonpath([str(file_to_serve), str(web_dir_resolved)]) == str(web_dir_resolved)
            except Exception:
                is_common = False

            # Prohibit serving hidden files, python code, and zip archives directly
            blocked_extensions = {".py", ".zip", ".7z"}
            has_blocked_ext = file_to_serve.suffix.lower() in blocked_extensions
            is_hidden = any(part.startswith(".") for part in file_to_serve.parts)

            if not (is_safe and is_common) or is_hidden or has_blocked_ext:
                self.send_error(403, "Access Denied: Path Traversal or Prohibited Resource")
                return

            if not file_to_serve.is_file() and path.startswith("/assets/"):
                ensure_assets(PROJECT_DIR)

            if file_to_serve.is_file():
                mime, _ = mimetypes.guess_type(str(file_to_serve))
                mime = mime or "application/octet-stream"
                with open(file_to_serve, "rb") as f:
                    content = f.read()

                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, f"File not found: {path}")
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception as ex:
            mem_patcher.log("ERROR", f"do_GET exception at {self.path}: {ex}")
            self.send_error(500, f"Internal Server Error: {ex}")

    def do_POST(self):
        try:
            if not self._is_allowed_origin():
                self._send_json({"success": False, "error": "Forbidden: Cross-Origin API Access Denied"}, status=403)
                return

            if not self._verify_token():
                self._send_json({"success": False, "error": "Forbidden: Invalid or missing X-Suite-Token header"}, status=403)
                return

            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/api/patch":
                body = self._read_json_body()
                allow_override = bool(body.get("allow_version_override", False))
                res = mem_patcher.patch_memory(allow_version_override=allow_override)
                status_code = 200 if res.get("success") else 400
                self._send_json(res, status=status_code)
                return

            elif path == "/api/unpatch":
                res = mem_patcher.unpatch_memory()
                status_code = 200 if res.get("success") else 400
                self._send_json(res, status=status_code)
                return

            elif path == "/api/auto-watch":
                body = self._read_json_body()
                enabled = bool(body.get("enabled", False))
                mem_patcher.set_auto_watch(enabled)
                self._send_json({"success": True, "auto_watch": mem_patcher.auto_watch_enabled})
                return

            elif path == "/api/logs/clear":
                mem_patcher.clear_logs()
                self._send_json({"success": True, "message": "Logs cleared."})
                return

            elif path == "/api/export-logs":
                res = mem_patcher.export_diagnostic_report()
                self._send_json(res)
                return

            elif path == "/api/inspect":
                # Run deep diagnostic inspection of live memory
                mem_patcher.log("DEBUG", "--- Running Deep Diagnostics Scan ---")
                status = mem_patcher.get_status()
                if status["is_running"]:
                    mem_patcher.log("DEBUG", f"Process PID: {status['pid']}, Base: {status['base_address']}")
                    tel = status["telemetry"]
                    mem_patcher.log("DEBUG", f"PlayerManager: {tel.get('player_manager_addr')}, Bits: {tel.get('bits'):,}, Gems: {tel.get('gems'):,}")
                    mem_patcher.log("DEBUG", f"TownManager: {tel.get('town_manager_addr')}, Current Zone: {tel.get('zone_name')} ({tel.get('current_zone')})")
                    mem_patcher.log("DEBUG", f"ShopManager: {tel.get('shop_manager_addr')}, Section Zone: {tel.get('shop_category_zone_name')} ({tel.get('shop_category_zone')}), Items: {tel.get('shop_items_total')}")
                    mem_patcher.log("DEBUG", f"Pending Store Item: {tel.get('pending_item')}")
                    mem_patcher.log("DEBUG", f"Town Store Isolation: {tel.get('zone_isolation_status')}")
                    for k, h in status["hooks"].items():
                        mem_patcher.log("DEBUG", f"Hook [{h['name']} @ {h['rva']}]: {'ACTIVE' if h['active'] else 'INACTIVE'}")
                else:
                    mem_patcher.log("WARN", "Target process is not running.")
                self._send_json({"success": True, "message": "Diagnostics completed."})
                return

            elif path == "/api/catalog/apply":
                body = self._read_json_body()
                selected_ids = body.get("selected_ids", None)
                res = mem_patcher.apply_pony_selection(selected_ids)
                self._send_json(res)
                return

            elif path == "/api/catalog/rescan":
                res = mem_patcher.rescan_catalog_from_ram()
                self._send_json(res)
                return

            self.send_error(404, "Endpoint not found")
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception as ex:
            mem_patcher.log("ERROR", f"do_POST exception at {self.path}: {ex}")
            self._send_json({"success": False, "error": f"Internal Server Error: {ex}"}, status=500)


def run_server(port: int = 8080):
    server_address = ("127.0.0.1", port)
    httpd = RobustThreadingHTTPServer(server_address, StoreSuiteRequestHandler)
    print(f"[SECURITY] Session Security Token generated: {SESSION_TOKEN}")
    print(f"MLPStoreSuite2 Server running at http://127.0.0.1:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port)
