# OBS Reaction Overlay

A program that briefly shows an image or video on your OBS screen when a specific
phrase appears in CHZZK chat.

**⬇️ [Download the latest Windows release](https://github.com/picaqwe104/Stream_Overray/releases/latest)** — unzip anywhere and double-click `OBS_Reaction_Overlay.exe`. No installation needed.

> Example: when a viewer types `?` in chat, an overlay you configured pops up on
> screen for a moment.

It runs **only on your own broadcasting PC** (`127.0.0.1`) and sends nothing to any
external server.

| Type `?` in chat → OBS | Control-page test button → OBS |
|:---:|:---:|
| ![Chat reaction demo](screenshots/demo2.gif) | ![Test button demo](screenshots/demo.gif) |

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
4. Click **입력값 테스트** (test) on the control page to confirm the overlay shows in OBS. (If you have no overlays yet, add one in step 4 first.)

## 4. Add an overlay (empty by default)

A fresh install has **no overlays** — you must add one before chat or the test
button does anything.

1. On the control page, click **반응 오버레이 → 오버레이 추가** (Reaction overlays → Add overlay).
2. Enter an overlay **name** (for your own reference).
3. **Upload** an image/video, or drop a file into the `assets` folder and type its filename.
   - Supported: `svg, webm, mp4, mov, gif, png, jpg, jpeg, webp`
   - You can test with the included `sample-ping.svg`.
   - Add several with **미디어 추가** (add media) and a **random** one plays on each trigger.
4. Add **trigger phrases**, one per line (e.g. `?`, `??`). A reaction fires only when chat **exactly matches** a phrase.
5. Tick **이 오버레이 사용** (use this overlay).
6. Click **전체 설정 저장** (save all settings).
7. Use **입력값 테스트** (test) to confirm it appears in OBS.

The **표시 방식** (display) panel controls position (random/fixed), size, padding, volume, and how many show at once.
Expand **개별 표시 설정** (per-overlay display) on an overlay card to give just that overlay its own size and position (unchecked = global values).
The **최근 반응** (recent reactions) panel shows, live, which chat triggered which overlay.

## Screenshots

**Control page** — configure triggers, overlays, position, size, and volume.

![Control page](screenshots/control-page.png)

**OBS browser source** — set the URL to `http://127.0.0.1:39291/overlay`.

![OBS browser source](screenshots/obs-setup.png)

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

## Credits / Attribution

This repository and the distribution package **bundle no game assets.** A fresh
install starts with an empty overlay list; you add your own media.

The question-mark ping shown in the demo GIFs is the **League of Legends "missing
ping" animation** (intellectual property of Riot Games, Inc.), shown **for
illustration only**. ([Obtained from](https://cromakeyuploader.tistory.com/entry/%EB%A1%A4-%EB%AC%BC%EC%9D%8C%ED%91%9C-%ED%95%91-LOL-question-mark-green-screen) — not the original source.)

If you add League of Legends / Riot Games assets **yourself**, Riot's
["Legal Jibber Jabber"](https://www.riotgames.com/en/legal) policy permits
**non-commercial fan use only** and requires this disclaimer:

> OBS Reaction Overlay was created under Riot Games' "Legal Jibber Jabber" policy using assets owned by Riot Games. Riot Games does not endorse or sponsor this project.

For commercial use (selling, donations, crowdfunding), use media you own or are
licensed to use. See [`THIRD_PARTY_LICENSES.txt`](THIRD_PARTY_LICENSES.txt). (Not legal advice.)

## License

The MIT license applies to **this project's code**; bundled media follows the
Credits above. See `LICENSE`.
