# 발표 데모 녹화 절차

경진대회 발표용 영상을 만드는 순서다. 총 재생 시간은 165초(2분 45초)이며, 자동 재생 한 번이
그대로 영상 한 편이 된다.

대상: 이 저장소를 처음 여는 사람. Isaac Sim 4.5 가 `C:\issac sim` 에 설치돼 있다고 가정한다.

---

## 1. 준비 (녹화 5분 전)

Isaac Sim 은 GPU 를 독점하므로 **Blender 를 먼저 종료한다.** 둘을 같이 띄우면 Isaac 의 RTX
초기화가 실패한다.

녹화 화면에 불필요한 것이 찍히지 않도록 정리한다.

- 편집기·브라우저·알림을 닫는다 (Windows 집중 지원을 켜면 팝업이 뜨지 않는다)
- 디스플레이 배율 100 %, 해상도 1920×1080 이상
- 노트북이면 전원 어댑터를 연결한다 (배터리 모드에서 GPU 클럭이 떨어져 프레임이 반토막 난다)

## 2. 데모 기동

```powershell
cd "C:\Users\sunwu\OneDrive\바탕 화면\프로젝트\디지털 트윈\크레인 퀀선 모터 모델링\motor_dt_viz"
C:\ISSACS~1\python.bat app\demo_integrated.py --gui
```

경로에 공백이 있어 `C:\issac sim\python.bat` 은 깨진다. 8.3 형식인 `C:\ISSACS~1\python.bat`
을 쓴다.

기동에 40초~1분이 걸린다. 창이 뜨면 다음을 확인한다.

- 왼쪽에 `VIGENT - Control` 패널, 오른쪽에 `VIGENT - Motor Digital Twin` HUD 가 보인다
- HUD 맨 아래 `SIMULATION-BASED ESTIMATE (not measured)` 문구가 잘리지 않고 보인다
- 뷰포트 중앙에 모터가 있고, 케이블이 왼쪽 위로 뻗어 초록 입자가 흐른다

**뷰포트에 "No lights found in stage" 알림이 떠 있으면 사라질 때까지 기다린다.** 기동 직후
잠깐 나타나며, 이 상태로 녹화를 시작하면 첫 장면에 그대로 찍힌다.

저사양 PC 라 프레임이 떨어지면 `--low` 를 붙인다. 해상도 1280×720, 입자 수와 물리 서브스텝이
절반이 된다.

```powershell
C:\ISSACS~1\python.bat app\demo_integrated.py --gui --low
```

## 3. 녹화 시작

Windows 기본 게임 바로 충분하다.

1. `Win + G` → 캡처 위젯의 ● 버튼 (또는 `Win + Alt + R`)
2. 녹화가 시작되면 **제어 패널의 `AUTO-PLAY SCENARIO` 를 누른다**
3. 165초 동안 손대지 않는다 — 시나리오가 부하·결함·전기 케이스를 스스로 바꾸고, 제어 패널의
   체크박스도 따라 움직인다
4. HUD 제목이 `5. Conclusion` 으로 바뀌고 15초가 지나면 `Win + Alt + R` 로 정지

영상은 `%USERPROFILE%\Videos\Captures` 에 저장된다.

게임 바가 Isaac Sim 창을 인식하지 못하면 ffmpeg 로 창을 직접 캡처한다.

```powershell
ffmpeg -f gdigrab -framerate 30 -i title="Isaac Sim Python 4.5.0" -c:v libx264 -preset fast -pix_fmt yuv420p demo.mp4
```

## 4. 시나리오 구성 (무엇이 언제 보이는가)

각 단계의 시간·자막·배속은 [`config/scenario.yaml`](../config/scenario.yaml) 에서 바꿀 수 있다.
`time_scale` 은 그 구간의 열 시뮬레이션 배속이다 (×120 이면 1초에 2분이 흐른다).

| 시각 | 단계 | 화면에서 일어나는 일 |
|---|---|---|
| 0–30 s | 1. 정상 운전 | 모든 부품이 원래 재질, 3상 전류 초록. I₂/I₁ 0.006 |
| 30–70 s | 2. DE 베어링 열화 | 구동측 베어링이 주황 → 빨강. 엔드실드가 반투명해져 안이 보인다. 전류는 아직 초록 |
| 70–105 s | 3. 턴간 단락 4턴 | A상 케이블·권선이 빨강으로. I₂/I₁ 0.006 → 0.104 |
| 105–150 s | 4. 턴간 단락 12턴 | A상 88 A (201 %). 권선 온도가 뒤따라 오르기 시작 |
| 150–165 s | 5. 결론 | 권선 130 °C WARNING. "조기 감지" 메시지 |

발표에서 짚을 지점은 **3단계**다. 베어링은 이미 빨간데 3상 전류는 아직 초록이다. 이 구간이
"고장이 눈에 보이기 전에 신호는 이미 나와 있다"는 주장의 근거이고, 5단계의 권선 과열이 그
신호를 놓쳤을 때의 결과다.

## 5. 한국어 자막 입히기

HUD 자막은 영문이다. Isaac Sim 4.5 의 omni.ui 기본 폰트에 한글 글리프가 없어 한글을 넣으면
`??` 로 깨지고, `style={"font": <ttf>}` 로 폰트를 지정해도 적용되지 않았다.

한국어 자막은 `scenario.yaml` 의 `subtitle` 필드에 그대로 들어 있다. 영상 편집기(클립챔프,
프리미어 등)에서 위 표의 시각에 맞춰 얹으면 된다.

## 6. 스크린샷만 필요할 때

발표 자료용 정지 이미지는 스크립트가 자동으로 뽑는다. 데모를 띄우고 단계 전환을 감지해
Isaac Sim 창만 잘라 5장을 저장한다.

```powershell
powershell -ExecutionPolicy Bypass -File tools\capture_demo.ps1
```

결과는 `docs/screenshots/p4_01_normal.png` ~ `p4_05_conclusion.png` 다. 파일 이름 앞부분은
`-Prefix` 로 바꿀 수 있다.

## 7. 잘 안 될 때

| 증상 | 원인과 해결 |
|---|---|
| 창이 뜨지 않고 바로 끝난다 | `logs/demo_integrated_error.txt` 를 본다. Blender 가 떠 있으면 종료한다 |
| 한글이 `??` 로 보인다 | HUD 는 영문만 쓴다. 한국어는 편집 자막으로 넣는다 (5절) |
| 프레임이 30 아래로 떨어진다 | `--low` 로 실행한다. 그래도 낮으면 다른 GPU 앱을 모두 닫는다 |
| 베어링이 빨간데 안 보인다 | 엔드실드 투시는 베어링이 warning 이상일 때만 켜진다. 2단계 중반까지 기다린다 |
| 입자가 안 흐른다 | 모드가 `Mechanical (heat)` 이면 전류 경로가 숨는다. `Integrated` 를 누른다 |

실행 중 기록은 `logs/demo_<날짜>.csv` 에 남는다 (온도 9노드, 3상 RMS, I₂/I₁, 진동, ISO 존,
FPS). 발표 후 수치를 되짚을 때 쓴다.
