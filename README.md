# OBS Reaction Overlay

[한국어 README](README.ko.md)

Local OBS browser-source overlay that reacts to CHZZK chat messages. The app runs a
local Python HTTP server on `127.0.0.1:39291`, serves a control page and overlay
page, connects to CHZZK OpenAPI sessions, and pushes overlay events to OBS through
Server-Sent Events.

## Current Status

This repository contains the public source and distribution files for the local
OBS overlay app. Live CHZZK long-run connection behavior should be validated
with your own CHZZK developer app before release builds are shared broadly.

Do not commit local credential or token files:

- `credentials.json`
- `chzzk_tokens.json`
- `chzzk_auth_state.json`
- `config.json`

## Project Layout

- `server.py`: local HTTP API, CHZZK auth/session client, SSE event broadcaster.
- `public/control.html`: local configuration UI.
- `public/overlay.html`: OBS browser-source page.
- `assets/`: public-safe sample overlay media.
- `README.txt`: end-user Windows package guide in Korean.
- `Build_Windows_Exe.bat`: PyInstaller one-folder Windows build helper.
- `Make_Distribution_Zip.bat`: local release ZIP helper.

## Development

Python 3.12+ is recommended.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python server.py
```

Open the control page:

```text
http://127.0.0.1:39291/control
```

OBS browser source URL:

```text
http://127.0.0.1:39291/overlay
```

Local health endpoint:

```text
http://127.0.0.1:39291/api/health
```

## Windows Build

Run:

```bat
Build_Windows_Exe.bat
Make_Distribution_Zip.bat
```

Generated files under `build/`, `dist/`, and `*.zip` are release artifacts and
should not be committed.

User-provided overlay media should be kept local unless you have the right to
redistribute it publicly.

## License

MIT. See `LICENSE`.
