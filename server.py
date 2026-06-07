from __future__ import annotations

import base64
import hashlib
import html
import json
import mimetypes
import os
import queue
import random
import re
import secrets
import socket
import ssl
import struct
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, unquote, urlparse

import requests


ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"
ASSETS_DIR = ROOT / "assets"
CONFIG_PATH = ROOT / "config.json"
CREDENTIALS_PATH = ROOT / "credentials.json"
TOKENS_PATH = ROOT / "chzzk_tokens.json"
AUTH_STATE_PATH = ROOT / "chzzk_auth_state.json"
HOST = "127.0.0.1"
PORT = 39291
APP_VERSION = "1.0.0"
OPENAPI_BASE_URL = "https://openapi.chzzk.naver.com"
AUTH_URL = "https://chzzk.naver.com/account-interlock"
SOCKET_READ_TIMEOUT_SEC = 10
WATCHDOG_MIN_STALE_SEC = 90
WATCHDOG_GRACE_SEC = 45
RECONNECT_INITIAL_DELAY_SEC = 2
RECONNECT_MAX_DELAY_SEC = 60
RECONNECT_JITTER_RATIO = 0.2
MAX_JSON_BODY_BYTES = 1_048_576
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
SERVER_STARTED_AT = time.time()

SUPPORTED_ASSET_EXTENSIONS = {
    ".svg",
    ".webm",
    ".mp4",
    ".mov",
    ".gif",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}

# Template used only to normalize user-defined overlays. No overlay ships by
# default: the initial config has an empty overlay list and the user adds their own.
DEFAULT_OVERLAY = {
    "id": "overlay",
    "name": "오버레이",
    "asset": "sample-ping.svg",
    "triggers": ["?"],
    "enabled": True,
}

DEFAULT_CONFIG = {
    "positionMode": "random",
    "x": 1260,
    "y": 360,
    "width": 150,
    "height": 150,
    "padding": 24,
    "maxVisible": 5,
    "volume": 100,
    "overlays": [],
}

clients: set[queue.Queue[str]] = set()
clients_lock = threading.Lock()
chzzk_state = {
    "connectionState": "stopped",
    "connected": False,
    "connecting": False,
    "lastMessage": "연결 안 됨",
    "sessionKey": "",
    "subscribed": False,
    "lastChat": "",
    "lastError": "",
    "lastFrameAt": 0,
    "lastChatAt": 0,
    "reconnects": 0,
    "lastReconnectAt": 0,
    "lastReconnectReason": "",
    "nextReconnectDelaySec": 0,
    "lastPingAt": 0,
    "lastPongAt": 0,
    "pingIntervalSec": 25,
    "pingTimeoutSec": 20,
}
chzzk_thread: threading.Thread | None = None
chzzk_watchdog_thread: threading.Thread | None = None
chzzk_websocket: SimpleWebSocket | None = None
chzzk_stop_event = threading.Event()
chzzk_lock = threading.Lock()


def normalize_overlay(raw_overlay: dict, index: int = 0) -> dict:
    overlay = dict(DEFAULT_OVERLAY)
    overlay["id"] = f"overlay-{index + 1}"
    overlay.update({key: raw_overlay[key] for key in overlay.keys() if key in raw_overlay})

    overlay["id"] = safe_id(str(overlay.get("id") or f"overlay-{index + 1}"))
    overlay["name"] = str(overlay.get("name") or "오버레이")
    overlay["asset"] = safe_asset_name(str(overlay.get("asset") or "sample-ping.svg"))
    overlay["triggers"] = normalize_triggers(overlay.get("triggers"))
    overlay["enabled"] = bool(overlay.get("enabled", True))
    return overlay


def normalize_config(raw_config: dict | None) -> dict:
    raw_config = raw_config or {}
    config = dict(DEFAULT_CONFIG)
    config.update({key: raw_config[key] for key in DEFAULT_CONFIG.keys() if key in raw_config})

    config["positionMode"] = config["positionMode"] if config["positionMode"] in ("random", "fixed") else "random"
    config["x"] = clamp_number(config.get("x"), 0, 7680, DEFAULT_CONFIG["x"])
    config["y"] = clamp_number(config.get("y"), 0, 4320, DEFAULT_CONFIG["y"])
    config["width"] = clamp_number(config.get("width"), 40, 1200, DEFAULT_CONFIG["width"])
    config["height"] = clamp_number(config.get("height"), 40, 1200, DEFAULT_CONFIG["height"])
    config["padding"] = clamp_number(config.get("padding"), 0, 1000, DEFAULT_CONFIG["padding"])
    config["maxVisible"] = int(clamp_number(config.get("maxVisible"), 1, 20, DEFAULT_CONFIG["maxVisible"]))
    config["volume"] = int(clamp_number(config.get("volume"), 0, 100, DEFAULT_CONFIG["volume"]))

    overlays = config.get("overlays")
    if not isinstance(overlays, list):
        overlays = []
    config["overlays"] = [normalize_overlay(item, index) for index, item in enumerate(overlays)]
    return config


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        config = normalize_config(DEFAULT_CONFIG)
        save_config(config)
        return config

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        loaded = json.load(file)

    config = normalize_config(loaded)
    if config != loaded:
        save_config(config)
    return config


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(normalize_config(config), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_credentials(masked: bool = True) -> dict:
    if not CREDENTIALS_PATH.exists():
        return {
            "clientId": "",
            "clientSecret": "",
            "redirectUri": f"http://{HOST}:{PORT}/auth/chzzk/callback",
            "configured": False,
        }

    with CREDENTIALS_PATH.open("r", encoding="utf-8") as file:
        credentials = json.load(file)

    client_secret = str(credentials.get("clientSecret", ""))
    client_id = str(credentials.get("clientId", ""))
    return {
        "clientId": mask_client_id(client_id) if masked else client_id,
        "clientSecret": mask_secret(client_secret) if masked else client_secret,
        "redirectUri": str(credentials.get("redirectUri", f"http://{HOST}:{PORT}/auth/chzzk/callback")),
        "configured": bool(credentials.get("clientId") and client_secret),
    }


def save_credentials(body: dict) -> dict:
    current = load_credentials(masked=False)
    client_id = str(body.get("clientId") or "")
    if client_id and set(client_id) == {"*"}:
        client_id = current.get("clientId", "")
    client_secret = str(body.get("clientSecret") or "")
    if set(client_secret) == {"*"}:
        client_secret = current.get("clientSecret", "")

    credentials = {
        "clientId": client_id.strip(),
        "clientSecret": client_secret.strip(),
        "redirectUri": str(
            body.get("redirectUri") or f"http://{HOST}:{PORT}/auth/chzzk/callback"
        ).strip(),
    }
    CREDENTIALS_PATH.write_text(
        json.dumps(credentials, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return load_credentials(masked=True)


def load_tokens() -> dict:
    if not TOKENS_PATH.exists():
        return {}
    with TOKENS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_tokens(tokens: dict) -> None:
    TOKENS_PATH.write_text(
        json.dumps(tokens, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def update_chzzk_state(**updates) -> None:
    updates.setdefault("lastStateChangedAt", int(time.time()))
    with chzzk_lock:
        chzzk_state.update(updates)
        snapshot = enrich_chzzk_state(dict(chzzk_state))
    broadcast({"type": "chzzk_status", "status": snapshot})


def enrich_chzzk_state(state: dict) -> dict:
    state["credentialsConfigured"] = load_credentials(masked=True)["configured"]
    tokens = load_tokens()
    state["loggedIn"] = bool(tokens.get("accessToken") or tokens.get("refreshToken"))
    if (state.get("connected") or state.get("connecting")) and chzzk_thread and not chzzk_thread.is_alive():
        state["connected"] = False
        state["connecting"] = False
        state["subscribed"] = False
        state["connectionState"] = "error"
        state["lastMessage"] = "연결 스레드 종료됨"
    state["connectionState"] = normalize_connection_state(state)
    return state


def get_chzzk_state() -> dict:
    with chzzk_lock:
        state = dict(chzzk_state)
    return enrich_chzzk_state(state)


def normalize_connection_state(state: dict) -> str:
    explicit_state = str(state.get("connectionState") or "")
    valid_states = {
        "stopped",
        "auth_required",
        "connecting",
        "connected",
        "subscribing",
        "subscribed",
        "stale",
        "backing_off",
        "error",
    }
    if explicit_state in valid_states:
        return explicit_state
    if state.get("subscribed"):
        return "subscribed"
    if state.get("connected"):
        return "connected"
    if state.get("connecting"):
        return "connecting"
    if state.get("lastError"):
        return "error"
    return "stopped"


def seconds_since(timestamp: int | float | None) -> int | None:
    if not timestamp:
        return None
    return max(0, int(time.time() - float(timestamp)))


def sse_client_count() -> int:
    with clients_lock:
        return len(clients)


def reconnect_delay_with_jitter(
    base_delay: float,
    jitter_ratio: float = RECONNECT_JITTER_RATIO,
    random_value: float | None = None,
) -> float:
    if jitter_ratio <= 0:
        return base_delay
    if random_value is None:
        random_value = random.random()
    spread = base_delay * jitter_ratio
    return max(0.0, base_delay - spread + (2 * spread * random_value))


def next_reconnect_delay(current_delay: float, connection_lived_sec: float) -> float:
    base_delay = RECONNECT_INITIAL_DELAY_SEC if connection_lived_sec >= 60 else current_delay
    return min(RECONNECT_MAX_DELAY_SEC, max(RECONNECT_INITIAL_DELAY_SEC, base_delay * 2))


def chzzk_error_requires_login(error_text: str) -> bool:
    auth_markers = (
        "로그인이 필요",
        "401",
        "invalid_token",
        "unauthorized",
        "권한이 해제",
    )
    lowered = error_text.lower()
    return any(marker.lower() in lowered for marker in auth_markers)


def build_health_status() -> dict:
    state = get_chzzk_state()
    config = load_config()
    return {
        "ok": True,
        "version": APP_VERSION,
        "server": {
            "host": HOST,
            "port": PORT,
            "uptimeSec": max(0, int(time.time() - SERVER_STARTED_AT)),
            "sseClients": sse_client_count(),
        },
        "chzzk": {
            "connectionState": state["connectionState"],
            "connected": bool(state.get("connected")),
            "connecting": bool(state.get("connecting")),
            "subscribed": bool(state.get("subscribed")),
            "credentialsConfigured": bool(state.get("credentialsConfigured")),
            "loggedIn": bool(state.get("loggedIn")),
            "lastFrameAgeSec": seconds_since(state.get("lastFrameAt")),
            "lastChatAgeSec": seconds_since(state.get("lastChatAt")),
            "reconnects": int(state.get("reconnects") or 0),
            "nextReconnectDelaySec": state.get("nextReconnectDelaySec", 0),
            "lastReconnectReason": state.get("lastReconnectReason", ""),
            "lastError": state.get("lastError", ""),
            "lastMessage": state.get("lastMessage", ""),
        },
        "settings": {
            "overlayCount": len(config.get("overlays", [])),
        },
    }


def is_local_request_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    host = parsed.hostname or ""
    if host not in {HOST, "localhost"}:
        return False
    return parsed.port in {None, PORT}


def mask_secret(value: str) -> str:
    if not value:
        return ""
    visible = min(4, len(value))
    return "*" * max(8, len(value) - visible) + value[-visible:]


def mask_client_id(value: str) -> str:
    if not value:
        return ""
    return "*" * max(8, len(value))


def broadcast(event: dict) -> None:
    payload = f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    with clients_lock:
        stale_clients = []
        for client in clients:
            try:
                client.put_nowait(payload)
            except queue.Full:
                stale_clients.append(client)

        for client in stale_clients:
            clients.discard(client)


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict:
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length == 0:
        return {}
    if content_length > MAX_JSON_BODY_BYTES:
        raise ValueError("JSON body too large")

    raw_body = handler.rfile.read(content_length)
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("Invalid JSON body") from error
    if not isinstance(parsed, dict):
        raise ValueError("JSON body must be an object")
    return parsed


def clamp_number(value, minimum, maximum, fallback):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, number))


def safe_id(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-")
    return value or f"overlay-{secrets.token_hex(3)}"


def safe_asset_name(value: str) -> str:
    return Path(value).name


def normalize_triggers(value) -> list[str]:
    if isinstance(value, str):
        parts = re.split(r"[\n,]+", value)
    elif isinstance(value, list):
        parts = value
    else:
        parts = []
    return [str(part).strip() for part in parts if str(part).strip()]


def overlay_matches(overlay: dict, content: str) -> bool:
    if not overlay.get("enabled", True):
        return False

    normalized_content = content.strip()
    for trigger in overlay.get("triggers", []):
        if normalized_content == trigger:
            return True
    return False


def find_overlay(config: dict, overlay_id: str | None = None, content: str | None = None) -> dict | None:
    overlays = config.get("overlays", [])
    if overlay_id:
        for overlay in overlays:
            if overlay["id"] == overlay_id:
                return overlay

    if content is not None:
        for overlay in overlays:
            if overlay_matches(overlay, content):
                return overlay

    return overlays[0] if overlays else None


def guess_level(content: str, overlay: dict) -> int:
    if content and set(content.strip()) == {"?"}:
        return min(3, max(1, len(content.strip())))
    trigger_count = len(overlay.get("triggers") or [])
    return min(3, max(1, trigger_count))


def build_overlay_event(
    overlay_id: str | None = None,
    content: str | None = None,
) -> tuple[dict | None, str | None]:
    config = load_config()
    overlay = find_overlay(config, overlay_id=overlay_id, content=content)
    if overlay is None:
        return None, "no_overlay_configured"

    if content is not None and not overlay_matches(overlay, content):
        return None, "no_matching_overlay"

    level = guess_level(content or "", overlay)
    return (
        {
            "type": "play_overlay",
            "level": level,
            "settings": config,
            "overlay": overlay,
            "sentAt": time.time(),
        },
        None,
    )


def trigger_overlay(
    overlay_id: str | None = None,
    content: str | None = None,
) -> tuple[bool, dict | None, str | None]:
    event, reason = build_overlay_event(overlay_id=overlay_id, content=content)
    if not event:
        return False, None, reason
    broadcast(event)
    return True, event, None


def api_post(path: str, payload: dict, access_token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    response = requests.post(
        f"{OPENAPI_BASE_URL}{path}",
        headers=headers,
        json=payload,
        timeout=10,
    )
    if not response.ok:
        raise RuntimeError(f"{response.status_code} {response.text}")
    return response.json()


def api_get(path: str, access_token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    response = requests.get(f"{OPENAPI_BASE_URL}{path}", headers=headers, timeout=10)
    if not response.ok:
        raise RuntimeError(f"{response.status_code} {response.text}")
    return response.json()


def response_content(response: dict):
    if not isinstance(response, dict):
        raise RuntimeError(f"예상하지 못한 API 응답 형식: {type(response).__name__}")
    return response.get("content", response)


def exchange_code_for_token(code: str, state: str) -> dict:
    credentials = load_credentials(masked=False)
    response = api_post(
        "/auth/v1/token",
        {
            "grantType": "authorization_code",
            "clientId": credentials["clientId"],
            "clientSecret": credentials["clientSecret"],
            "code": code,
            "state": state,
        },
    )
    content = response_content(response)
    content["expiresAt"] = int(time.time()) + int(content.get("expiresIn", 86400)) - 120
    save_tokens(content)
    return content


def refresh_access_token() -> dict:
    credentials = load_credentials(masked=False)
    tokens = load_tokens()
    refresh_token = tokens.get("refreshToken")
    if not refresh_token:
        raise RuntimeError("치지직 로그인이 필요합니다.")

    response = api_post(
        "/auth/v1/token",
        {
            "grantType": "refresh_token",
            "refreshToken": refresh_token,
            "clientId": credentials["clientId"],
            "clientSecret": credentials["clientSecret"],
        },
    )
    content = response_content(response)
    content["expiresAt"] = int(time.time()) + int(content.get("expiresIn", 86400)) - 120
    save_tokens(content)
    return content


def get_valid_access_token() -> str:
    tokens = load_tokens()
    if tokens.get("accessToken") and int(tokens.get("expiresAt", 0)) > int(time.time()):
        return tokens["accessToken"]
    return refresh_access_token()["accessToken"]


def create_session_url(access_token: str) -> str:
    response = api_get("/open/v1/sessions/auth", access_token=access_token)
    content = response_content(response)
    session_url = content.get("url")
    if not session_url:
        raise RuntimeError("세션 URL을 받지 못했습니다.")
    return session_url


def subscribe_chat(session_key: str, access_token: str) -> None:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        f"{OPENAPI_BASE_URL}/open/v1/sessions/events/subscribe/chat",
        headers=headers,
        params={"sessionKey": session_key},
        timeout=10,
    )
    if not response.ok:
        raise RuntimeError(f"{response.status_code} {response.text}")


def build_socketio_websocket_url(session_url: str) -> str:
    parsed = urlparse(session_url)
    scheme = "wss" if parsed.scheme in ("https", "wss") else "ws"
    query = dict(parse_qsl(parsed.query))
    query["EIO"] = "3"
    query["transport"] = "websocket"
    path = parsed.path if parsed.path and parsed.path != "/" else "/socket.io/"
    return f"{scheme}://{parsed.netloc}{path}?{urlencode(query)}"


class SimpleWebSocket:
    def __init__(self, url: str):
        self.url = url
        self.parsed = urlparse(url)
        self.sock: ssl.SSLSocket | socket.socket | None = None

    def connect(self) -> None:
        port = self.parsed.port or (443 if self.parsed.scheme == "wss" else 80)
        host = self.parsed.hostname
        if not host:
            raise RuntimeError("WebSocket host가 없습니다.")

        raw_sock = socket.create_connection((host, port), timeout=10)
        if self.parsed.scheme == "wss":
            context = ssl.create_default_context()
            self.sock = context.wrap_socket(raw_sock, server_hostname=host)
        else:
            self.sock = raw_sock

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = self.parsed.path or "/"
        if self.parsed.query:
            path += f"?{self.parsed.query}"
        host_header = self.parsed.netloc
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host_header}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Origin: https://chzzk.naver.com\r\n"
            "\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = self._read_http_response()
        if " 101 " not in response.split("\r\n", 1)[0]:
            raise RuntimeError(f"WebSocket 연결 실패: {response.splitlines()[0]}")

        expected = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        if expected not in response:
            raise RuntimeError("WebSocket 핸드셰이크 검증 실패")
        self.sock.settimeout(SOCKET_READ_TIMEOUT_SEC)

    def _read_http_response(self) -> str:
        assert self.sock is not None
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data.decode("iso-8859-1", errors="replace")

    def send_text(self, text: str) -> None:
        self._send_frame(0x1, text.encode("utf-8"))

    def send_pong(self, payload: bytes = b"") -> None:
        self._send_frame(0xA, payload)

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        assert self.sock is not None
        mask_key = os.urandom(4)
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        masked = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + mask_key + masked)

    def recv_text(self) -> str | None:
        while True:
            opcode, payload = self._recv_frame()
            if opcode == 0x8:
                return None
            if opcode == 0x9:
                self.send_pong(payload)
                return ""  # WS-level ping 수신 — 호출자가 lastFrameAt을 갱신하도록 빈 문자열 반환
            if opcode == 0x1:
                return payload.decode("utf-8", errors="replace")
            # 0x0 continuation, 0x2 binary, 0xA pong 등 미처리 opcode → 무시

    def _recv_frame(self) -> tuple[int, bytes]:
        assert self.sock is not None
        first = self._recv_exact(2)
        opcode = first[0] & 0x0F
        masked = bool(first[1] & 0x80)
        length = first[1] & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask_key = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length)
        if masked:
            payload = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))
        return opcode, payload

    def _recv_exact(self, length: int) -> bytes:
        assert self.sock is not None
        data = b""
        while len(data) < length:
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                raise RuntimeError("WebSocket 연결이 끊겼습니다.")
            data += chunk
        return data

    def close(self) -> None:
        if self.sock:
            self.sock.close()
            self.sock = None


def handle_socketio_message(message: str, access_token: str) -> None:
    update_chzzk_state(lastFrameAt=int(time.time()))
    if message.startswith("0"):
        return
    if message == "40":
        update_chzzk_state(connectionState="connected", lastMessage="소켓 연결 완료")
        return
    if message == "2":
        raise RuntimeError("internal_ping")
    if not message.startswith("42"):
        return

    payload_text = message[2:].strip()
    if not payload_text:
        return
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        update_chzzk_state(lastMessage=f"알 수 없는 소켓 프레임 무시: {message[:40]}")
        return
    if not isinstance(payload, list) or len(payload) < 2:
        return

    event_type = payload[0]
    body = payload[1] or {}
    if isinstance(body, str):
        if not body.strip():
            return
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            body = {"content": body}
    if not isinstance(body, dict):
        return

    if event_type == "SYSTEM":
        system_type = body.get("type")
        data = body.get("data") or {}
        if isinstance(data, str):
            if not data.strip():
                data = {}
            else:
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    data = {}
        if not isinstance(data, dict):
            data = {}
        if system_type == "connected":
            session_key = data.get("sessionKey", "")
            update_chzzk_state(
                connectionState="subscribing",
                connected=True,
                sessionKey=session_key,
                lastMessage="채팅 이벤트 구독 중",
            )
            subscribe_chat(session_key, access_token)
            return
        if system_type == "subscribed":
            update_chzzk_state(
                connectionState="subscribed",
                subscribed=True,
                nextReconnectDelaySec=0,
                lastMessage="채팅 이벤트 구독 완료",
            )
            return
        if system_type == "revoked":
            update_chzzk_state(
                connectionState="auth_required",
                subscribed=False,
                lastError="치지직 권한이 해제되었습니다.",
            )
            return

    if event_type == "CHAT":
        content = str(body.get("content", ""))
        nickname = ((body.get("profile") or {}).get("nickname")) or ""
        ok, _, reason = trigger_overlay(content=content)
        update_chzzk_state(
            lastChat=f"{nickname}: {content}" if nickname else content,
            lastChatAt=int(time.time()),
            lastMessage="채팅 수신" if ok else f"채팅 수신, 매칭 없음: {reason}",
        )


def run_chzzk_once() -> None:
    global chzzk_websocket
    websocket = None
    ping_interval = 25
    next_ping_at = time.time() + ping_interval
    update_chzzk_state(
        connectionState="connecting",
        connecting=True,
        connected=False,
        subscribed=False,
        lastError="",
        lastMessage="Access Token 확인 중",
    )
    access_token = get_valid_access_token()
    update_chzzk_state(lastMessage="세션 URL 요청 중")
    session_url = create_session_url(access_token)
    websocket_url = build_socketio_websocket_url(session_url)
    websocket = SimpleWebSocket(websocket_url)
    chzzk_websocket = websocket  # watchdog이 참조할 수 있도록 전역에 노출
    try:
        websocket.connect()
        update_chzzk_state(
            connectionState="connected",
            connecting=False,
            connected=True,
            subscribed=False,
            lastFrameAt=int(time.time()),
            lastMessage="소켓 초기화 중",
        )
        websocket.send_text("40")

        while not chzzk_stop_event.is_set():
            now = time.time()
            if now >= next_ping_at:
                # Chzzk 세션은 EIO=3(Socket.IO v2 계열)로 연결한다.
                # Engine.IO v3에서는 클라이언트가 ping(2)을 보내고 서버가 pong(3)으로 응답한다.
                websocket.send_text("2")
                update_chzzk_state(lastPingAt=int(now), lastMessage="소켓 heartbeat 전송")
                next_ping_at = now + ping_interval

            try:
                message = websocket.recv_text()
            except socket.timeout:
                # 채팅이 없는 조용한 시간에는 아무 프레임도 오지 않을 수 있다.
                # read timeout은 중지/재연결 요청에 반응하기 위한 polling 용도이고,
                # 실제 stale 연결 판정은 watchdog에서 더 긴 기준으로만 처리한다.
                continue
            # OSError(네트워크 단절, 소켓 강제 종료 등)는 잡지 않고 즉시 상위로 전파 → 재연결
            if message is None:
                raise RuntimeError("소켓이 종료되어 재연결합니다.")
            if message == "":
                # WebSocket-level ping (opcode 0x9)을 수신하고 pong을 보낸 경우 — 연결 살아있음 확인
                update_chzzk_state(lastFrameAt=int(time.time()))
                continue
            if message.startswith("0"):
                # Engine.IO open 프레임 — pingInterval / pingTimeout 파싱 후 소켓 타임아웃 동적 조정
                try:
                    data = json.loads(message[1:])
                    ping_interval = max(5, int(data.get("pingInterval", 25000)) // 1000)
                    ping_timeout = max(5, int(data.get("pingTimeout", 20000)) // 1000)
                    update_chzzk_state(
                        pingIntervalSec=ping_interval,
                        pingTimeoutSec=ping_timeout,
                        lastFrameAt=int(time.time()),
                    )
                    next_ping_at = time.time() + ping_interval
                    websocket.sock.settimeout(SOCKET_READ_TIMEOUT_SEC)
                except Exception:
                    update_chzzk_state(lastFrameAt=int(time.time()))
                continue
            if message == "2":
                update_chzzk_state(lastFrameAt=int(time.time()), lastMessage="소켓 heartbeat 수신")
                websocket.send_text("3")
                continue
            if message == "3":
                update_chzzk_state(
                    lastFrameAt=int(time.time()),
                    lastPongAt=int(time.time()),
                    lastMessage="소켓 heartbeat 응답 수신",
                )
                continue
            handle_socketio_message(message, access_token)
    finally:
        chzzk_websocket = None
        websocket.close()


def chzzk_session_loop() -> None:
    retry_delay = RECONNECT_INITIAL_DELAY_SEC
    while not chzzk_stop_event.is_set():
        started_at = time.time()
        try:
            run_chzzk_once()
        except Exception as error:
            if chzzk_stop_event.is_set():
                break
            error_text = str(error)
            if chzzk_error_requires_login(error_text):
                update_chzzk_state(
                    connectionState="auth_required",
                    connected=False,
                    connecting=False,
                    subscribed=False,
                    nextReconnectDelaySec=0,
                    lastError=error_text,
                    lastReconnectReason=error_text,
                    lastMessage="치지직 로그인이 필요합니다.",
                )
                break
            connection_lived_sec = time.time() - started_at
            if connection_lived_sec >= 60:
                retry_delay = RECONNECT_INITIAL_DELAY_SEC
            wait_delay = reconnect_delay_with_jitter(retry_delay)
            current = get_chzzk_state()
            update_chzzk_state(
                connectionState="backing_off",
                connected=False,
                connecting=False,
                subscribed=False,
                reconnects=int(current.get("reconnects") or 0) + 1,
                lastReconnectAt=int(time.time()),
                lastReconnectReason=error_text,
                lastError=error_text,
                nextReconnectDelaySec=round(wait_delay, 1),
                lastMessage=f"재연결 대기 중 ({wait_delay:.1f}초)",
            )
            chzzk_stop_event.wait(wait_delay)
            retry_delay = next_reconnect_delay(retry_delay, connection_lived_sec)
        else:
            connection_lived_sec = time.time() - started_at
            if connection_lived_sec >= 60:
                retry_delay = RECONNECT_INITIAL_DELAY_SEC
            wait_delay = reconnect_delay_with_jitter(retry_delay)
            if not chzzk_stop_event.is_set():
                update_chzzk_state(
                    connectionState="backing_off",
                    connected=False,
                    connecting=False,
                    subscribed=False,
                    nextReconnectDelaySec=round(wait_delay, 1),
                    lastMessage=f"소켓 종료, 재연결 대기 중 ({wait_delay:.1f}초)",
                )
                chzzk_stop_event.wait(wait_delay)
            retry_delay = next_reconnect_delay(retry_delay, connection_lived_sec)

    if get_chzzk_state().get("connectionState") != "auth_required":
        update_chzzk_state(
            connectionState="stopped",
            connected=False,
            connecting=False,
            subscribed=False,
            nextReconnectDelaySec=0,
        )


def chzzk_watchdog_loop() -> None:
    """독립 감시 스레드.

    채팅이 없는 방송에서는 Socket.IO 프레임이 오래 비어 있을 수 있으므로 짧은 heartbeat 기준으로
    재연결하지 않는다. 실제로 오래 멈춘 stale 연결만 보수적으로 닫아 재연결을 유도한다.
    """
    while not chzzk_stop_event.is_set():
        chzzk_stop_event.wait(15)  # 15초마다 점검 (빠른 좀비 감지)
        if chzzk_stop_event.is_set():
            break
        state = get_chzzk_state()
        # 연결 중이 아닐 때는 점검 불필요
        if not (state.get("connected") or state.get("subscribed")):
            continue
        last_frame = state.get("lastFrameAt", 0)
        if last_frame == 0:
            continue
        elapsed = time.time() - last_frame
        # 동적 임계값 + 여유. 클라이언트가 25초마다 ping을 보내 프레임이 계속 오므로
        # 채팅이 없어도 거짓 재연결은 없다. 기본값 기준 max(90, 25 + 20 + 45) = 90초.
        threshold = max(
            WATCHDOG_MIN_STALE_SEC,
            state.get("pingIntervalSec", 25) + state.get("pingTimeoutSec", 20) + WATCHDOG_GRACE_SEC,
        )
        if elapsed > threshold:
            update_chzzk_state(
                connectionState="stale",
                lastMessage=f"Watchdog: {int(elapsed)}초간 응답 없음 — 재연결 중",
                lastError=f"Watchdog: {int(elapsed)}초간 Socket.io 응답 없음",
            )
            ws = chzzk_websocket
            if ws:
                ws.close()  # recv_text()에서 OSError/RuntimeError 발생 → 재연결 루프로 진입


def start_chzzk_session() -> None:
    global chzzk_thread, chzzk_watchdog_thread
    if chzzk_thread and chzzk_thread.is_alive():
        update_chzzk_state(lastMessage="이미 연결 중입니다.")
        return
    update_chzzk_state(connectionState="connecting", lastError="", lastMessage="채팅 연결 시작")
    chzzk_stop_event.clear()
    chzzk_thread = threading.Thread(target=chzzk_session_loop, daemon=True)
    chzzk_thread.start()
    chzzk_watchdog_thread = threading.Thread(target=chzzk_watchdog_loop, daemon=True)
    chzzk_watchdog_thread.start()


def restart_chzzk_session() -> None:
    global chzzk_thread, chzzk_watchdog_thread
    chzzk_stop_event.set()
    ws = chzzk_websocket
    if ws:
        ws.close()  # 블로킹된 recv_text()를 즉시 깨워 이전 세션 스레드가 빨리 종료되게 한다
    if chzzk_thread and chzzk_thread.is_alive():
        chzzk_thread.join(timeout=SOCKET_READ_TIMEOUT_SEC + 2)
    if chzzk_watchdog_thread and chzzk_watchdog_thread.is_alive():
        chzzk_watchdog_thread.join(timeout=2)
    if chzzk_thread and chzzk_thread.is_alive():
        # 이전 세션 스레드가 아직 살아 있는데 stop_event를 풀고 새 스레드를 띄우면
        # 좀비 스레드가 되살아나 같은 사용자로 중복 연결이 생긴다(유저당 최대 3연결 제한).
        # 종료가 확인될 때까지 stop 상태를 유지하고, 재시도는 사용자에게 맡긴다.
        update_chzzk_state(
            connectionState="stopped",
            lastMessage="이전 연결 종료 대기 중입니다. 잠시 후 다시 시도하세요.",
        )
        return
    chzzk_thread = None
    chzzk_watchdog_thread = None
    chzzk_stop_event.clear()
    update_chzzk_state(
        connectionState="connecting",
        connected=False,
        connecting=False,
        subscribed=False,
        lastError="",
        lastMessage="채팅 재연결 시작",
    )
    start_chzzk_session()


def stop_chzzk_session() -> None:
    chzzk_stop_event.set()
    ws = chzzk_websocket
    if ws:
        ws.close()  # 소켓을 즉시 닫아 서버 측 연결도 빠르게 정리(유저당 최대 3연결 제한 대비)
    update_chzzk_state(
        connectionState="stopped",
        connected=False,
        connecting=False,
        subscribed=False,
        nextReconnectDelaySec=0,
        lastError="",
        lastMessage="연결 중지 요청",
    )


def parse_multipart_upload(handler: BaseHTTPRequestHandler) -> tuple[str, bytes]:
    content_type = handler.headers.get("Content-Type", "")
    match = re.search(r"boundary=(.+)", content_type)
    if not match:
        raise ValueError("multipart boundary missing")

    boundary = match.group(1).strip().strip('"').encode("utf-8")
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length > MAX_UPLOAD_BYTES:
        raise ValueError("uploaded file is too large")
    body = handler.rfile.read(content_length)

    for part in body.split(b"--" + boundary):
        if b"Content-Disposition" not in part or b"filename=" not in part:
            continue
        header_blob, _, file_blob = part.partition(b"\r\n\r\n")
        disposition = header_blob.decode("utf-8", errors="ignore")
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        if not filename_match:
            continue
        filename = safe_asset_name(filename_match.group(1))
        file_blob = file_blob.rstrip(b"\r\n")
        if file_blob.endswith(b"--"):
            file_blob = file_blob[:-2]
        return filename, file_blob

    raise ValueError("file field missing")


class PingOverlayHandler(BaseHTTPRequestHandler):
    server_version = f"OBSReactionOverlay/{APP_VERSION}"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/control"):
            self.send_static(PUBLIC_DIR / "control.html", "text/html; charset=utf-8")
            return

        if path == "/overlay":
            self.send_static(PUBLIC_DIR / "overlay.html", "text/html; charset=utf-8")
            return

        if path == "/api/settings":
            self.send_json(load_config())
            return

        if path == "/api/chzzk-credentials":
            self.send_json(load_credentials(masked=True))
            return

        if path == "/api/chzzk-status":
            self.send_json(get_chzzk_state())
            return

        if path == "/api/health":
            self.send_json(build_health_status())
            return

        if path == "/auth/chzzk/start":
            self.start_chzzk_auth()
            return

        if path == "/auth/chzzk/callback":
            self.handle_chzzk_callback(parsed)
            return

        if path == "/events":
            self.handle_events()
            return

        if path.startswith("/assets/"):
            self.send_asset(path.removeprefix("/assets/"))
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self.is_allowed_mutation_origin():
            self.send_json({"ok": False, "error": "Forbidden origin"}, HTTPStatus.FORBIDDEN)
            return

        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/settings":
            self.update_settings()
            return

        if path == "/api/chzzk-credentials":
            body = self.read_json_body()
            if body is None:
                return
            self.send_json(save_credentials(body))
            return

        if path == "/api/assets":
            self.upload_asset()
            return

        if path == "/api/test-ping":
            body = self.read_json_body()
            if body is None:
                return
            self.play_overlay(overlay_id=body.get("overlayId"), force=True)
            return

        if path == "/api/chat-simulate":
            body = self.read_json_body()
            if body is None:
                return
            content = str(body.get("content", ""))
            self.play_overlay(content=content)
            return

        if path == "/api/chzzk-connect":
            start_chzzk_session()
            self.send_json(get_chzzk_state())
            return

        if path == "/api/chzzk-reconnect":
            restart_chzzk_session()
            self.send_json(get_chzzk_state())
            return

        if path == "/api/chzzk-disconnect":
            stop_chzzk_session()
            self.send_json(get_chzzk_state())
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def read_json_body(self) -> dict | None:
        try:
            return parse_json_body(self)
        except ValueError as error:
            self.send_json({"ok": False, "error": str(error)}, HTTPStatus.BAD_REQUEST)
            return None

    def is_allowed_mutation_origin(self) -> bool:
        origin = self.headers.get("Origin", "")
        referer = self.headers.get("Referer", "")
        if origin and origin != "null" and not is_local_request_url(origin):
            return False
        if referer and not is_local_request_url(referer):
            return False
        return True

    def start_chzzk_auth(self) -> None:
        credentials = load_credentials(masked=False)
        if not credentials.get("clientId") or not credentials.get("clientSecret"):
            self.send_error(HTTPStatus.BAD_REQUEST, "Client ID/Secret을 먼저 저장하세요.")
            return

        state = secrets.token_urlsafe(24)
        AUTH_STATE_PATH.write_text(json.dumps({"state": state}), encoding="utf-8")
        query = urlencode(
            {
                "clientId": credentials["clientId"],
                "redirectUri": credentials["redirectUri"],
                "state": state,
            }
        )
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", f"{AUTH_URL}?{query}")
        self.end_headers()

    def handle_chzzk_callback(self, parsed) -> None:
        params = dict(parse_qsl(parsed.query))
        code = params.get("code")
        state = params.get("state")
        expected_state = ""
        if AUTH_STATE_PATH.exists():
            expected_state = json.loads(AUTH_STATE_PATH.read_text(encoding="utf-8")).get("state", "")

        if not code or not state or state != expected_state:
            self.send_html("치지직 로그인 실패", "state가 맞지 않습니다. 컨트롤 페이지에서 다시 로그인하세요.")
            return

        try:
            exchange_code_for_token(code, state)
            update_chzzk_state(lastMessage="치지직 로그인 완료")
            self.send_html(
                "치지직 로그인 완료",
                "토큰 저장이 완료되었습니다. 컨트롤 페이지로 돌아가서 채팅 연결 시작을 누르세요.",
            )
        except Exception as error:
            update_chzzk_state(lastError=str(error), lastMessage="토큰 발급 실패")
            self.send_html("치지직 로그인 실패", str(error))

    def update_settings(self) -> None:
        body = self.read_json_body()
        if body is None:
            return
        current = load_config()
        next_config = dict(current)
        next_config["x"] = clamp_number(body.get("x"), 0, 7680, current["x"])
        next_config["y"] = clamp_number(body.get("y"), 0, 4320, current["y"])
        next_config["width"] = clamp_number(body.get("width"), 40, 1200, current["width"])
        next_config["height"] = clamp_number(body.get("height"), 40, 1200, current["height"])
        next_config["padding"] = clamp_number(body.get("padding"), 0, 1000, current["padding"])
        next_config["maxVisible"] = int(
            clamp_number(body.get("maxVisible"), 1, 20, current["maxVisible"])
        )
        next_config["volume"] = int(clamp_number(body.get("volume"), 0, 100, current.get("volume", 100)))
        position_mode = str(body.get("positionMode", current["positionMode"]))
        next_config["positionMode"] = position_mode if position_mode in ("random", "fixed") else "random"

        overlays = body.get("overlays", current["overlays"])
        next_config["overlays"] = [
            normalize_overlay(overlay, index) for index, overlay in enumerate(overlays)
        ]

        save_config(next_config)
        broadcast({"type": "settings", "settings": next_config})
        self.send_json(next_config)

    def upload_asset(self) -> None:
        try:
            filename, data = parse_multipart_upload(self)
        except ValueError as error:
            status = HTTPStatus.REQUEST_ENTITY_TOO_LARGE if "too large" in str(error) else HTTPStatus.BAD_REQUEST
            self.send_json({"ok": False, "error": str(error)}, status)
            return

        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_ASSET_EXTENSIONS:
            self.send_json(
                {
                    "ok": False,
                    "error": "지원 형식: svg, webm, mp4, mov, gif, png, jpg, jpeg, webp",
                },
                HTTPStatus.BAD_REQUEST,
            )
            return

        ASSETS_DIR.mkdir(exist_ok=True)
        destination = ASSETS_DIR / unique_asset_name(filename)
        destination.write_bytes(data)
        self.send_json({"ok": True, "asset": destination.name, "url": f"/assets/{destination.name}"})

    def play_overlay(
        self,
        overlay_id: str | None = None,
        content: str | None = None,
        force: bool = False,
    ) -> None:
        config = load_config()
        overlay = find_overlay(config, overlay_id=overlay_id, content=content)
        if overlay is None:
            self.send_json({"ok": False, "reason": "no_overlay_configured"})
            return

        if content is not None and not overlay_matches(overlay, content):
            self.send_json({"ok": False, "reason": "no_matching_overlay"})
            return

        level = guess_level(content or "", overlay)
        event = {
            "type": "play_overlay",
            "level": level,
            "settings": config,
            "overlay": overlay,
            "sentAt": time.time(),
        }
        broadcast(event)
        self.send_json({"ok": True, "event": event})

    def handle_events(self) -> None:
        client: queue.Queue[str] = queue.Queue(maxsize=100)
        with clients_lock:
            clients.add(client)

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        initial = {
            "type": "settings",
            "settings": load_config(),
        }
        self.wfile.write(f"data: {json.dumps(initial, ensure_ascii=False)}\n\n".encode("utf-8"))
        status = {"type": "chzzk_status", "status": get_chzzk_state()}
        self.wfile.write(f"data: {json.dumps(status, ensure_ascii=False)}\n\n".encode("utf-8"))
        self.wfile.flush()

        try:
            while True:
                try:
                    payload = client.get(timeout=15)
                except queue.Empty:
                    payload = ": keepalive\n\n"
                self.wfile.write(payload.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with clients_lock:
                clients.discard(client)

    def send_asset(self, asset_name: str) -> None:
        asset_name = safe_asset_name(unquote(asset_name))
        self.send_static(ASSETS_DIR / asset_name)

    def send_static(self, path: Path, content_type: str | None = None) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        if content_type is None:
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_html(self, title: str, message: str) -> None:
        safe_title = html.escape(title)
        safe_message = html.escape(message)
        body = f"""<!doctype html>
<html lang="ko">
  <head><meta charset="utf-8"><title>{safe_title}</title></head>
  <body style="font-family: system-ui, sans-serif; padding: 32px;">
    <h1>{safe_title}</h1>
    <p>{safe_message}</p>
    <p><a href="/control">컨트롤 페이지로 돌아가기</a></p>
  </body>
</html>""".encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        print("[%s] %s" % (self.log_date_time_string(), format % args))


def unique_asset_name(filename: str) -> str:
    safe_name = safe_asset_name(filename)
    stem = Path(safe_name).stem or "asset"
    suffix = Path(safe_name).suffix.lower()
    candidate = f"{safe_id(stem)}{suffix}"
    index = 2
    while (ASSETS_DIR / candidate).exists():
        candidate = f"{safe_id(stem)}-{index}{suffix}"
        index += 1
    return candidate


def main() -> None:
    ASSETS_DIR.mkdir(exist_ok=True)
    load_config()
    address = (HOST, PORT)
    server = ThreadingHTTPServer(address, PingOverlayHandler)
    print(f"Mia ping local server: http://{HOST}:{PORT}/control")
    print(f"OBS overlay URL:        http://{HOST}:{PORT}/overlay")
    if getattr(sys, "frozen", False) or os.environ.get("OPEN_CONTROL_ON_START") == "1":
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{HOST}:{PORT}/control")).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
