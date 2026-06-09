# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[한국어 변경 내역](CHANGELOG.md)

## [Unreleased]

## [1.2.0] - 2026-06-09

### Added
- Action-feedback **toasts** on the control page: saving settings, uploading
  media, and CHZZK connect/reconnect now show a success/failure toast.
  Success/info toasts auto-dismiss; failures show the reason plus a short code
  (e.g. `SET-400`) and stay until dismissed.
- The control-page footer shows the server version and a "refresh your OBS
  browser source after updating" note. (The overlay logs its version to the
  console / `?debug` to help spot a stale cache.)

### Fixed
- A per-overlay display size left blank now **inherits the global size** instead
  of defaulting to 150; the width/height inputs show the current global value as
  a placeholder.
- Saving no longer reports "saved" on failure (and no longer lets an error
  response overwrite the form): failures now show the reason and a code and
  leave the form untouched.

## [1.1.0] - 2026-06-09

### Added
- Per-overlay media pool: add several media files to one overlay and a random
  one plays on each trigger (single-media overlays are unchanged).
- Reaction log on the control page: a live list of which chat message triggered
  which overlay (and which media), kept in memory (last 50) and shown
  immediately when the page opens. Simulated/test reactions appear too, so it
  works without a CHZZK connection.
- Per-overlay display override: optionally give an overlay its own size and
  position (random/fixed) instead of the global values. Collapsed by default;
  edge padding and max-visible stay global.
- Overlays now clear within a few seconds when the server stops or the SSE
  connection drops, so nothing lingers frozen on screen (a brief reconnect does
  not wipe active reactions).

## [1.0.0] - 2026-06-08

First public release.

### Added
- Local OBS browser-source overlay that reacts to CHZZK chat: when a chat
  message exactly matches a configured trigger phrase, the chosen media
  (webm / mp4 / mov / gif / png / jpg / webp / svg) plays at a random or fixed
  position inside the OBS browser source.
- Control page to add overlays and configure triggers, media, position, size,
  edge padding, volume, and how many show at once. A fresh install starts with
  no overlays — you add your own media. Settings and connection status update
  live over Server-Sent Events.
- CHZZK OpenAPI integration: OAuth login, realtime session over Socket.IO
  (Engine.IO v3), chat-event subscription, and automatic access-token refresh.
- Resilient connection: a client-initiated heartbeat keeps the socket alive
  during quiet chat, a watchdog reconnects only on genuinely stale sockets, and
  reconnects use exponential backoff with jitter.
- Overlays auto-hide so they never linger on screen (images after a few seconds;
  videos when playback ends, with a safety timeout).
- Localhost-only server with origin/referer checks on mutations, masked
  credentials in API responses, and sanitized asset uploads.
- Windows one-folder build (`Build_Windows_Exe.bat`) and shareable package ZIP
  (`Make_Distribution_Zip.bat`); local credential and token files are excluded.
- App version exposed via `/api/health` and the HTTP `Server` header.

[Unreleased]: https://github.com/picaqwe104/Stream_Overray/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/picaqwe104/Stream_Overray/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/picaqwe104/Stream_Overray/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/picaqwe104/Stream_Overray/releases/tag/v1.0.0
