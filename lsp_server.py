"""
Laudas LSP server.

A minimal Language Server Protocol implementation for Laudas. Speaks LSP over
stdio. Watches `textDocument/didOpen` and `textDocument/didChange` events; on
each, runs the parser + voronin and emits diagnostics back to the editor.

Wire it into VS Code by adding a thin client extension (or by configuring
generic-lsp). For Neovim, configure `nvim-lspconfig` or call vim.lsp.start.

Run (for testing):
    python lsp_server.py        # speaks LSP over stdin/stdout

Status: scaffold. Implements initialize, initialized, didOpen, didChange,
didClose, shutdown, exit. Emits parse errors and verifier failures as
diagnostics. Does not yet implement: completion, hover, goto definition,
formatting, code actions.

Wire format compatibility: targets LSP 3.17 (current as of 2024).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Any, Optional


# ---------- LSP protocol I/O ----------

def _read_message() -> Optional[dict]:
    """Read one LSP message: Content-Length header + JSON body."""
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.decode("ascii")
        if line == "\r\n" or line == "\n":
            break
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    length = int(headers.get("Content-Length", "0"))
    body = sys.stdin.buffer.read(length).decode("utf-8")
    return json.loads(body)


def _send_message(msg: dict) -> None:
    body = json.dumps(msg).encode("utf-8")
    sys.stdout.buffer.write(b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n")
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def _send_response(req_id: Any, result: Any = None, error: Optional[dict] = None) -> None:
    msg: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    _send_message(msg)


def _send_notification(method: str, params: Any) -> None:
    _send_message({"jsonrpc": "2.0", "method": method, "params": params})


# ---------- Diagnostics from laudas.py ----------

def _laudas_command() -> list[str]:
    """Return the command to invoke laudas. Falls back to running laudas.py
    directly if `laudas` isn't on PATH."""
    here = os.path.dirname(os.path.abspath(__file__))
    laudas_py = os.path.join(here, "laudas.py")
    return [sys.executable, laudas_py]


def _run_laudas_check(text: str) -> str:
    """Write text to a temp .laud file, run `laudas FILE`, return combined output."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".laud", delete=False, encoding="utf-8") as f:
        f.write(text)
        tmp_path = f.name
    try:
        result = subprocess.run(
            _laudas_command() + [tmp_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        return (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired:
        return "error: laudas timed out"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


_loc_re = re.compile(r"location:\s*([^:]+):(\d+)")


def _parse_diagnostics(uri: str, output: str) -> list[dict]:
    """Best-effort extraction of diagnostics from laudas check output."""
    diags: list[dict] = []
    # Look for structured payload JSON blocks
    for m in re.finditer(r"\{[^{}]*\"error\"[^{}]*\"location\"[^{}]*\}", output, flags=re.DOTALL):
        try:
            payload = json.loads(m.group(0))
        except Exception:
            continue
        loc = payload.get("location", "")
        line = 0
        m_loc = _loc_re.search(f"location: {loc}")
        if m_loc:
            try:
                line = max(0, int(m_loc.group(2)) - 1)
            except ValueError:
                line = 0
        diags.append({
            "range": {
                "start": {"line": line, "character": 0},
                "end":   {"line": line, "character": 80},
            },
            "severity": 1,  # 1=error, 2=warn, 3=info, 4=hint
            "source": "voronin" if payload.get("error", "").startswith("verification") else "laudas",
            "message": payload.get("explanation") or payload.get("found") or payload.get("error", ""),
        })
    return diags


def _publish_diagnostics(uri: str, text: str) -> None:
    output = _run_laudas_check(text)
    diags = _parse_diagnostics(uri, output)
    _send_notification("textDocument/publishDiagnostics", {
        "uri": uri,
        "diagnostics": diags,
    })


# ---------- LSP request handlers ----------

_documents: dict[str, str] = {}


def _handle_initialize(req_id: Any, params: dict) -> None:
    _send_response(req_id, {
        "capabilities": {
            "textDocumentSync": 1,  # 1 = full document on each change
            "diagnosticProvider": {
                "interFileDependencies": False,
                "workspaceDiagnostics": False,
            },
        },
        "serverInfo": {
            "name": "laudas-lsp",
            "version": "0.1.0",
        },
    })


def _handle_did_open(params: dict) -> None:
    uri = params["textDocument"]["uri"]
    text = params["textDocument"]["text"]
    _documents[uri] = text
    _publish_diagnostics(uri, text)


def _handle_did_change(params: dict) -> None:
    uri = params["textDocument"]["uri"]
    changes = params.get("contentChanges", [])
    if changes and "text" in changes[-1]:
        text = changes[-1]["text"]
        _documents[uri] = text
        _publish_diagnostics(uri, text)


def _handle_did_close(params: dict) -> None:
    uri = params["textDocument"]["uri"]
    _documents.pop(uri, None)
    _send_notification("textDocument/publishDiagnostics", {"uri": uri, "diagnostics": []})


# ---------- Main loop ----------

def main() -> int:
    while True:
        msg = _read_message()
        if msg is None:
            return 0
        method = msg.get("method")
        req_id = msg.get("id")

        if method == "initialize":
            _handle_initialize(req_id, msg.get("params", {}))
        elif method == "initialized":
            pass
        elif method == "textDocument/didOpen":
            _handle_did_open(msg.get("params", {}))
        elif method == "textDocument/didChange":
            _handle_did_change(msg.get("params", {}))
        elif method == "textDocument/didClose":
            _handle_did_close(msg.get("params", {}))
        elif method == "shutdown":
            _send_response(req_id, None)
        elif method == "exit":
            return 0
        elif req_id is not None:
            # Unimplemented request — return method-not-found.
            _send_response(req_id, error={"code": -32601, "message": f"method {method!r} not implemented"})
        # Notifications without id can be silently ignored.


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
