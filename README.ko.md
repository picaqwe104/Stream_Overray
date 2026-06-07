# OBS Reaction Overlay

[English README](README.md)

치지직 채팅에 특정 문구가 올라오면 OBS 브라우저 소스 위에 WebM, MP4,
GIF, PNG 같은 오버레이를 띄우는 로컬 프로그램입니다.

이 앱은 외부 서버가 아니라 방송하는 PC에서 실행됩니다. 로컬 Python 서버가
`127.0.0.1:39291`에서 컨트롤 페이지와 OBS 오버레이 페이지를 제공하고,
치지직 OpenAPI 세션을 통해 받은 채팅 이벤트를 OBS로 전달합니다.

## 현재 상태

이 저장소는 공개용 소스와 배포에 필요한 파일만 포함합니다. 실제 배포 전에
본인의 치지직 Developers 앱으로 장시간 연결 동작을 검증하는 것을 권장합니다.

로컬 credential/token 파일은 커밋하지 마세요.

- `credentials.json`
- `chzzk_tokens.json`
- `chzzk_auth_state.json`
- `config.json`

## 구성

- `server.py`: 로컬 HTTP API, 치지직 인증/세션 연결, SSE 이벤트 브로드캐스트
- `public/control.html`: 설정 컨트롤 페이지
- `public/overlay.html`: OBS 브라우저 소스 페이지
- `assets/`: 공개 배포 가능한 샘플 오버레이 미디어
- `README.txt`: Windows 배포 패키지용 상세 사용설명서
- `Build_Windows_Exe.bat`: PyInstaller Windows 빌드 스크립트
- `Make_Distribution_Zip.bat`: 공유용 ZIP 생성 스크립트

## 개발 실행

Python 3.12 이상을 권장합니다.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python server.py
```

컨트롤 페이지:

```text
http://127.0.0.1:39291/control
```

OBS 브라우저 소스 URL:

```text
http://127.0.0.1:39291/overlay
```

상태 확인 API:

```text
http://127.0.0.1:39291/api/health
```

## Windows 빌드

아래 파일을 실행합니다.

```bat
Build_Windows_Exe.bat
Make_Distribution_Zip.bat
```

`build/`, `dist/`, `*.zip`은 배포 산출물입니다. 저장소에는 커밋하지 않습니다.

사용자가 직접 추가한 오버레이 미디어는 공개 재배포 권리가 확실한 경우에만
저장소에 포함하세요.

## OBS 설정 요약

1. OBS에서 브라우저 소스를 추가합니다.
2. URL에 `http://127.0.0.1:39291/overlay`를 입력합니다.
3. 브라우저 소스 크기를 오버레이가 나타날 영역에 맞춥니다.
4. 컨트롤 페이지에서 오버레이와 반응 채팅 문구를 설정합니다.
5. `입력값 테스트`로 OBS에 오버레이가 보이는지 확인합니다.

## 치지직 연동 요약

1. 치지직 Developers에서 애플리케이션을 등록합니다.
2. Redirect URI는 `http://127.0.0.1:39291/auth/chzzk/callback`로 설정합니다.
3. 컨트롤 페이지에 Client ID와 Client Secret을 저장합니다.
4. 치지직 로그인을 완료합니다.
5. `채팅 연결 시작`을 눌러 연결 상태와 구독 상태를 확인합니다.

## 라이선스

MIT. 자세한 내용은 `LICENSE`를 확인하세요.
