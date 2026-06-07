# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Attribution and the Riot Games "Legal Jibber Jabber" disclaimer for the bundled
  League of Legends sample animation (`mia-ping-alpha.webm`).

### Changed
- README now shows a download link to the latest release at the top.
- The main `README.md` is now Korean; the English version moved to `README.en.md`.
- README now includes demo GIFs and screenshots (control page, OBS source setup).

## [1.0.0] - 2026-06-07

First public release.

### Added
- Local OBS browser-source overlay that reacts to CHZZK chat: when a chat
  message exactly matches a configured trigger phrase, the matching media
  (webm / mp4 / mov / gif / png / jpg / webp / svg) plays at a random or fixed
  position inside the OBS browser source.
- Control page (`/control`) to configure triggers, overlay media, position,
  size, edge padding, volume, and how many overlays show at once; settings and
  connection status update live over Server-Sent Events.
- CHZZK OpenAPI integration: OAuth login, realtime session over Socket.IO
  (Engine.IO v3), chat-event subscription, and automatic access-token refresh.
- Resilient connection: a client-initiated heartbeat keeps the socket alive
  during quiet chat, a watchdog reconnects only on genuinely stale sockets, and
  reconnects use exponential backoff with jitter.
- Overlays auto-hide so they never linger on screen (images after a few
  seconds; videos when playback ends, with a safety timeout).
- Localhost-only server with origin/referer checks on mutations, masked
  credentials in API responses, and sanitized asset uploads.
- Windows one-folder build (`Build_Windows_Exe.bat`) and shareable package ZIP
  (`Make_Distribution_Zip.bat`); local credential and token files are excluded.
- `mia-ping-alpha.webm` sample overlay.
- App version exposed via `/api/health` and the HTTP `Server` header.

[Unreleased]: https://github.com/picaqwe104/Stream_Overray/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/picaqwe104/Stream_Overray/releases/tag/v1.0.0
