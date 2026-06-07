# OBS Reaction Overlay

A program that briefly shows an image or video on your OBS screen when a specific
phrase appears in CHZZK chat.

**⬇️ [Download the latest Windows release](https://github.com/picaqwe104/Stream_Overray/releases/latest)** — unzip anywhere and double-click `OBS_Reaction_Overlay.exe`. No installation needed.

> Example: when a viewer types `?` in chat, an overlay you configured pops up on
> screen for a moment.

It runs **only on your own broadcasting PC** (`127.0.0.1`) and sends nothing to any
external server.

_🎬 A demo GIF will be added soon._
<!-- Save the demo GIF as screenshots/demo.gif, then uncomment the line below and remove the note above. -->
<!-- ![Demo](screenshots/demo.gif) -->

[한국어 README](README.md)

## What you need

- OBS (your streaming software)
- This program (a Windows executable, or Python)
- A **CHZZK app key** to read chat — free; see step 2 below

## 1. Run the program

**A. From the executable (easiest, recommended)**

1. Unzip the folder you received.
2. Double-click `OBS_Reaction_Overlay.exe`.
3. The control page opens automatically after a moment. (If not → http://127.0.0.1:39291/control )
4. The black window that appears is the server. **Don't close it while streaming.**

**B. From source (for developers)**

```bash
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python server.py
```

Then open http://127.0.0.1:39291/control in your browser.

## 2. Get and register a CHZZK app key (needed for chat)

To read real chat you need your own CHZZK app key. It's **free and a one-time** setup.

1. Open the CHZZK developer center and sign in. → https://developers.chzzk.naver.com
2. Register a new application. Any name is fine, but avoid official service names like `chzzk`, `치지직`, `naver`, `네이버`.
3. Set the **login redirect URL** to exactly:
   ```
   http://127.0.0.1:39291/auth/chzzk/callback
   ```
4. For the permission (scope), select **read chat messages** (채팅 메시지 조회).
5. After registering you get a **Client ID** and **Client Secret**.
   Treat the Client Secret like a password — never share it.
6. On the control page ( http://127.0.0.1:39291/control ), paste the Client ID and
   Client Secret into **치지직 앱 정보** and click **앱 정보 저장** (save). They are
   masked on screen after saving.
7. Click **치지직 로그인** (log in) and approve the permission.
8. Click **채팅 연결 시작** (start). When the status shows `연결: 연결됨` (connected)
   and `구독: 완료` (subscribed), you're ready.

> Your keys are saved **only on your PC** in `credentials.json` / `chzzk_tokens.json`.
> If you share the folder with someone, leave those files out.

## 3. Connect the overlay to OBS

1. In OBS, add a source → **Browser**.
2. Set the URL to:
   ```
   http://127.0.0.1:39291/overlay
   ```
3. Size the browser source to the area where overlays should appear.
4. Click **입력값 테스트** (test) on the control page to confirm the overlay shows in OBS.

## 4. Configure phrases and overlays

On the control page you set which chat phrases to react to, which image/video to
show, and position / size / volume / how many show at once. A reaction fires only
when the chat content **exactly matches** a phrase.

## Screenshots

_📸 Control page and OBS setup screenshots will be added soon (see the `screenshots/` folder)._
<!-- Add the files, then uncomment the lines below. -->
<!-- ![Control page](screenshots/control-page.png) -->
<!-- ![OBS browser source](screenshots/obs-setup.png) -->

## Troubleshooting

- Nothing in OBS → check the browser source URL is `http://127.0.0.1:39291/overlay`, then use **입력값 테스트**.
- No chat coming in → check the status reads connected/subscribed, click **재연결** (reconnect); if it still fails, log in again with **치지직 로그인**.
- For detailed step-by-step instructions, see `README.txt` (Korean).

## Development & build

- Build a Windows executable: run `Build_Windows_Exe.bat`, then `Make_Distribution_Zip.bat`.
- Layout: `server.py` (local server, CHZZK integration, SSE broadcast),
  `public/control.html` (settings UI), `public/overlay.html` (OBS page), `assets/` (media).
- Health endpoint: http://127.0.0.1:39291/api/health
- `build/`, `dist/`, `*.zip` and local key files (`credentials.json`,
  `chzzk_tokens.json`, `chzzk_auth_state.json`, `config.json`) are not committed.

## Versioning

This project follows [Semantic Versioning](https://semver.org/) (`vMAJOR.MINOR.PATCH`).
Notable changes are recorded in [CHANGELOG.md](CHANGELOG.md), and each release is published
on the [GitHub Releases](https://github.com/picaqwe104/Stream_Overray/releases) page with the
Windows package attached. Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).

## License

MIT. See `LICENSE`.
