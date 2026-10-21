# 퇴역 모터 YAML (2026-10-21, 파트 C P2′)

사용자 결정: 디지털트윈은 현대 HLP-2.2/4(M1) 한 대로 간다. 호이스트 4종 라이브러리(M2~M5, source: representative)는 만들지 않는다.
이 폴더는 로더(`engine/motor_library.list_ids`)가 읽지 않는다(파일만 보관, 삭제 금지). `motor_M5_reference.yaml` 은 이전 `config/motor.yaml`(22 kW 6극, 열회로 튜닝 기준) 원본이다 —
열회로 스케일 기준값은 `config/thermal.yaml reference` 절로 옮겼다. `source: representative` 등급은 로더에서 더 이상 허용하지 않는다(여기에만 남음).
