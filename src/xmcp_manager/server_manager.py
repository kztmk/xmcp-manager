from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path

import httpx

from xmcp_manager import paths
from xmcp_manager.log_redactor import redact_line, redact_text
from xmcp_manager.models import (
    Account,
    ApiCredentials,
    AppSettings,
    ServerState,
    ServerStateSnapshot,
    StartResult,
    StateListener,
    StopResult,
    UnmanagedServerStatus,
)


class ServerManager:
    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._state = ServerStateSnapshot()
        self._logs: deque[str] = deque(maxlen=1000)
        self._listeners: list[StateListener] = []
        self._log_queue: queue.Queue[str] = queue.Queue()
        self._startup_timeout_sec = 300
        self._run_id = 0

    def subscribe(self, listener: StateListener) -> Callable[[], None]:
        self._listeners.append(listener)
        listener(self.get_state())

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def _publish(self) -> None:
        snapshot = self.get_state()
        for listener in list(self._listeners):
            listener(snapshot)

    def _set_state(self, state: ServerState, message: str = "") -> None:
        self._state.state = state
        self._state.message = message
        self._publish()

    def _append_log(self, line: str) -> None:
        redacted = redact_line(line.rstrip())
        self._logs.append(redacted)
        self._state.logs = list(self._logs)[-100:]
        self._log_queue.put(redacted)
        self._publish()

    def _read_output(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            self._append_log(line)

    def start(
        self,
        account: Account,
        credentials: ApiCredentials,
        allowlist: str | None,
        app_settings: AppSettings,
    ) -> StartResult:
        unmanaged = self.detect_unmanaged(app_settings.endpoint_url)
        if unmanaged.detected and self._process is None:
            return StartResult(ok=False, message=unmanaged.message)
        self.stop()
        self._run_id += 1
        run_id = self._run_id
        env = os.environ.copy()
        env.update(
            {
                "X_OAUTH_CONSUMER_KEY": credentials.consumer_key,
                "X_OAUTH_CONSUMER_SECRET": credentials.consumer_secret,
                "X_BEARER_TOKEN": credentials.bearer_token,
                "MCP_HOST": app_settings.mcp_host,
                "MCP_PORT": str(app_settings.mcp_port),
                "X_OAUTH_CALLBACK_HOST": app_settings.oauth_callback_host,
                "X_OAUTH_CALLBACK_PORT": str(app_settings.oauth_callback_port),
                "X_OAUTH_CALLBACK_PATH": app_settings.oauth_callback_path,
                "X_OAUTH_CALLBACK_TIMEOUT": "300",
                "X_OAUTH_PRINT_TOKENS": "0",
                "X_OAUTH_PRINT_AUTH_HEADER": "0",
            }
        )
        if allowlist is not None:
            env["X_API_TOOL_ALLOWLIST"] = allowlist
        server_path = paths.get_vendored_xmcp_dir() / "server.py"
        self._state.account_id = account.id
        self._state.account_label = account.label
        self._set_state(ServerState.STARTING, "Starting xmcp server.")
        self._process = subprocess.Popen(
            [sys.executable, str(server_path)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(server_path.parent),
        )
        threading.Thread(target=self._read_output, args=(self._process,), daemon=True).start()
        threading.Thread(
            target=self._watch_startup,
            args=(self._process, app_settings.endpoint_url, run_id),
            daemon=True,
        ).start()
        return StartResult(ok=True, message="xmcp server starting.")

    def _watch_startup(
        self,
        process: subprocess.Popen[str],
        endpoint_url: str,
        run_id: int,
    ) -> None:
        started_at = time.time()
        while process.poll() is None and time.time() - started_at < self._startup_timeout_sec:
            if run_id != self._run_id or process is not self._process:
                return
            while not self._log_queue.empty():
                line = self._log_queue.get_nowait()
                if "Opening browser for OAuth1 consent" in line or "OAuth" in line:
                    self._set_state(ServerState.WAITING_AUTH, "Waiting for OAuth authentication.")
            if self._probe_connectable(endpoint_url):
                self._set_state(ServerState.CONNECTABLE, "xmcp server is connectable.")
                return
            time.sleep(1)
        if run_id != self._run_id or process is not self._process:
            return
        if process.poll() is None:
            self._set_state(
                ServerState.ERROR,
                (
                    "Startup timed out. Check OAuth completion, callback URL, network access, "
                    "OpenAPI fetch, and port conflicts."
                ),
            )
        else:
            self._set_state(ServerState.ERROR, f"xmcp exited with code {process.returncode}.")

    def _probe_connectable(self, endpoint_url: str) -> bool:
        # Prefer a real MCP client when one is available. Fallback to a minimal JSON-RPC
        # initialize request because FastMCP Streamable HTTP support may be version-dependent.
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "xmcp-manager-probe", "version": "0.1.0"},
                },
            }
            response = httpx.post(endpoint_url, json=payload, timeout=2)
            return response.status_code < 500 and "jsonrpc" in response.text
        except Exception:
            return False

    def stop(self) -> StopResult:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        self._run_id += 1
        self._process = None
        self._state.account_id = None
        self._state.account_label = None
        self._set_state(ServerState.STOPPED, "xmcp server stopped.")
        return StopResult(ok=True, message="xmcp server stopped.")

    def detect_unmanaged(self, endpoint: str) -> UnmanagedServerStatus:
        if self._process and self._process.poll() is None:
            return UnmanagedServerStatus(detected=False, endpoint_url=endpoint)
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "xmcp-manager-detect", "version": "0.1.0"},
                },
            }
            response = httpx.post(endpoint, json=payload, timeout=1)
            if response.status_code < 500 and "jsonrpc" in response.text:
                return UnmanagedServerStatus(
                    detected=True,
                    endpoint_url=endpoint,
                    message=f"Another process is responding at {endpoint}.",
                )
        except Exception:
            pass
        return UnmanagedServerStatus(detected=False, endpoint_url=endpoint)

    def get_state(self) -> ServerStateSnapshot:
        return ServerStateSnapshot(
            state=self._state.state,
            account_id=self._state.account_id,
            account_label=self._state.account_label,
            message=self._state.message,
            logs=list(self._logs)[-100:],
        )

    def copy_logs(self) -> str:
        return redact_text("\n".join(self._logs))


def server_path() -> Path:
    return paths.get_vendored_xmcp_dir() / "server.py"
