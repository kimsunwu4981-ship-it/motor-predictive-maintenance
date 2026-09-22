# 영상 ↔ 차트 동기 검증 절차 (기준: 0.2 초 이내)

대시보드는 영상의 `currentTime` 을 단일 시간 소스로 쓰고, 차트·설명·상태 뱃지는 전부
`t_real = currentTime − video_offset_s` 로 계산한다. 따라서 동기 오차는 **오프셋 값의 정확도**로
결정되며, 오프셋은 녹화 시점에 두 겹으로 확정한다.

1. 데모(`motor_dt_viz/app/demo_integrated.py --record`)가 ffmpeg 기동 시각과 시나리오 시작 시각의
   차이를 `logs/<mode>/recording_<mode>_full.json` 의 `video_offset_s` 에 자동 기록한다.
2. HUD 에 구운 타임코드(`t 60.02s`)를 영상 프레임에서 읽어 1의 값과 대조한다.

`tools/export_dashboard_data.py` 는 1의 값을 그대로 `public/data/<mode>/scenarios.json` 에 넣는다.

## 녹화 시 실측 (2026-09-22)

| 모드 | 오프셋 | 검증 지점 (영상 시각 → 화면 타임코드) | 오차 |
|---|---|---|---|
| 기계 | 2.006 s | 22 s → 20.07 / 92 s → 90.07 / 167 s → 165.06 | +0.08 / +0.08 / +0.07 s |
| 전기 | 2.008 s | 22 s → 20.03 / 84 s → 82.04 / 152 s → 150.04 | +0.04 / +0.05 / +0.05 s |

드리프트 없음(시간이 지나도 오차가 커지지 않음). 검증 프레임은 `motor_dt_viz/logs/<mode>/sync_check/` 에 있다.

## 대시보드에서 직접 확인하는 법 (발표 전 1분)

1. `run_dashboard_mechanical.bat` 로 연다.
2. 주소 끝에 `?t=60` 을 붙인다: `http://localhost:4173/#/mechanical?t=60`
   → 차트 커서와 재생 시각 표시가 1:00 에 놓이고, 영상은 62.006 s 로 이동한다.
3. 영상 오른쪽 위 HUD 의 타임코드를 읽는다. **`t 60.0x s`** 이면 정상이다.
   0.2 s 를 넘게 어긋나면 오프셋이 잘못 들어간 것이므로 `recording_*.json` 과 `scenarios.json` 의
   `video_offset_s` 를 대조한다.
4. 전기 모드도 같은 방법으로 `#/electrical?t=120` 에서 확인한다.

재생 중에도 같은 원리다. 차트 아래 시각 표시와 영상 속 타임코드가 항상 같은 값을 가리켜야 한다.

## 기계 실시간 해설 대시보드 — 영상·차트·단면도 동기 (기준 0.2 초)

`#/mechanical` 의 온도 차트 커서, 진동 차트 커서, 모터 단면도 색, 상단 시뮬레이션 경과, 실시간 해설의 수치는
**모두 같은 `t_real` 값 하나에서** 계산된다(`state/playback.ts` 의 `t`). 따라서 서로 간 오차는 0 이고,
영상 대비 오차는 위와 같은 오프셋 정확도(≤ 0.08 s)로 결정된다.

직접 확인: `#/mechanical?t=27.5` 를 연다 → 영상 타임코드 `t 27.5x s`, 차트 커서가 "■ 위험 도달" 빨간 선 위,
단면도의 DE 베어링이 빨강 발광(위험), 상단 뱃지 "위험". 네 곳이 같은 순간을 가리키면 정상이다.
단면도 색이 영상 속 부품 색과 같은지는 `dashboard/tests/test_mechanical_extras.py::test_colormap_exported_equals_colors_yaml`
이 컬러맵 원본(`config/colors.yaml`)과 대조한다.

## 왜 헤드리스 스크린샷으로는 이 검증을 못 하나

헤드리스 브라우저는 영상 프레임을 그리지 않아(검은 화면) 타임코드를 읽을 수 없다.
그래서 이 검증은 실제 브라우저에서 사람이 한 번 눈으로 한다. 로직 자체(오프셋 덧셈)는
`dashboard/tests/test_export.py::test_scenario_steps_match_yaml` 이 `video_start = t_start + offset` 으로 검사한다.
