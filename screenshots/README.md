# 스크린샷 / 데모 미디어

메인 `README.md`(와 `README.en.md`)에서 참조하는 이미지·GIF를 이 폴더에 넣습니다.
아래 **파일명 그대로** 저장한 뒤, README에서 `<!-- -->` 로 주석 처리된 이미지 줄의 주석만
풀면 바로 표시됩니다.

| 파일명 | 내용 | 권장 |
|---|---|---|
| `demo.gif` | 채팅 입력 → 오버레이가 뜨는 동작 데모 | 가로 ~800px, 5~10초, 5MB 이하 |
| `control-page.png` | 컨트롤 페이지 화면 | 가로 ~1000px |
| `obs-setup.png` | OBS 브라우저 소스 설정 화면 | 가로 ~1000px |

## 넣는 방법
1. 위 파일명으로 이 `screenshots/` 폴더에 저장합니다.
2. `README.md` 에서 해당 이미지의 `<!-- ![...](screenshots/...) -->` 줄에서 `<!--` 와 `-->` 를
   제거하고, 그 위의 "준비 중" 안내 줄은 지웁니다. (`README.en.md` 도 동일)
3. 커밋: `git add screenshots README.md README.en.md && git commit -m "docs: add screenshots"`

> 이 폴더는 GitHub README 표시에만 쓰이며, Windows 배포 패키지에는 포함되지 않습니다.
