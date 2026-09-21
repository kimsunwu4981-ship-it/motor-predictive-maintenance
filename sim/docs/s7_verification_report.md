# S7 — 신호 검증 보고 (이론 vs 검출 주파수)

- 데이터셋: `sim/output/dataset_v01` (`generation: analytic_injection`)
- 분석 채널: 조인트 각가속도(정속 구간 6 s, 분해능 Δf = 0.1667 Hz), 베어링 결함은 힐베르트 포락선 스펙트럼
- 판정: |검출 − 이론| ≤ Δf 이고 피크 두드러짐(주변 중앙값 대비) > 3

| 결함 | 심각도 | 부하 | rpm | 분석 | 이론 Hz | 검출 Hz | 오차 Hz | 두드러짐 | 판정 |
|---|---|---|---|---|---|---|---|---|---|
| brb | incipient | noload | 1199.86 | fft | 0.014 | — | — | — | N/A |
| brb | moderate | noload | 1199.57 | fft | 0.043 | — | — | — | N/A |
| brb | severe | noload | 1199.39 | fft | 0.061 | — | — | — | N/A |
| brb | incipient | rated | 1170.71 | fft | 2.929 | 3.0 | 0.0707 | 1255.3 | ✅ |
| brb | moderate | rated | 1170.86 | fft | 2.914 | 2.833 | 0.0808 | 605.2 | ✅ |
| brb | severe | rated | 1171.52 | fft | 2.848 | 2.833 | 0.0149 | 326.7 | ✅ |
| ecc_static | e10 | noload | 1200.0 | fft | 120.0 | 120.0 | 0.0 | 8082.9 | ✅ |
| ecc_static | e20 | noload | 1200.0 | fft | 120.0 | 120.0 | 0.0 | 20564.8 | ✅ |
| ecc_static | e30 | noload | 1200.0 | fft | 120.0 | 120.0 | 0.0 | 47747.2 | ✅ |
| ecc_static | e10 | rated | 1170.7 | fft | 120.0 | 120.0 | 0.0 | 30862.1 | ✅ |
| ecc_static | e20 | rated | 1170.7 | fft | 120.0 | 120.0 | 0.0 | 51729.0 | ✅ |
| ecc_static | e30 | rated | 1170.7 | fft | 120.0 | 120.0 | 0.0 | 119434.9 | ✅ |
| ecc_dynamic | e10 | noload | 1200.0 | fft | 20.0 | 19.833 | 0.1667 | 4665.1 | ✅ |
| ecc_dynamic | e10 | noload | 1200.0 | fft | 100.0 | 100.167 | 0.1667 | 1503.4 | ✅ |
| ecc_dynamic | e10 | noload | 1200.0 | fft | 140.0 | 139.833 | 0.1667 | 1453.7 | ✅ |
| ecc_dynamic | e20 | noload | 1200.0 | fft | 20.0 | 19.833 | 0.1667 | 9130.2 | ✅ |
| ecc_dynamic | e20 | noload | 1200.0 | fft | 100.0 | 100.167 | 0.1667 | 2391.2 | ✅ |
| ecc_dynamic | e20 | noload | 1200.0 | fft | 140.0 | 139.833 | 0.1667 | 2087.9 | ✅ |
| ecc_dynamic | e30 | noload | 1200.0 | fft | 20.0 | 19.833 | 0.1667 | 13950.6 | ✅ |
| ecc_dynamic | e30 | noload | 1200.0 | fft | 100.0 | 100.167 | 0.1667 | 4136.1 | ✅ |
| ecc_dynamic | e30 | noload | 1200.0 | fft | 140.0 | 139.833 | 0.1667 | 4618.9 | ✅ |
| ecc_dynamic | e10 | rated | 1170.7 | fft | 19.512 | 19.667 | 0.155 | 7953.2 | ✅ |
| ecc_dynamic | e10 | rated | 1170.7 | fft | 100.488 | 100.333 | 0.155 | 2581.3 | ✅ |
| ecc_dynamic | e10 | rated | 1170.7 | fft | 139.512 | 139.667 | 0.155 | 2510.9 | ✅ |
| ecc_dynamic | e20 | rated | 1170.7 | fft | 19.512 | 19.667 | 0.155 | 7154.1 | ✅ |
| ecc_dynamic | e20 | rated | 1170.7 | fft | 100.488 | 100.333 | 0.155 | 4266.4 | ✅ |
| ecc_dynamic | e20 | rated | 1170.7 | fft | 139.512 | 139.667 | 0.155 | 4138.0 | ✅ |
| ecc_dynamic | e30 | rated | 1170.7 | fft | 19.512 | 19.5 | 0.0116 | 5696.0 | ✅ |
| ecc_dynamic | e30 | rated | 1170.7 | fft | 100.488 | 100.5 | 0.0116 | 5023.8 | ✅ |
| ecc_dynamic | e30 | rated | 1170.7 | fft | 139.512 | 139.5 | 0.0116 | 5258.5 | ✅ |
| itsc | t2 | noload | 1200.0 | fft | 120.0 | 120.0 | 0.0 | 6571.1 | ✅ |
| itsc | t2 | noload | 1200.0 | fft | 40.0 | 40.167 | 0.1666 | 1901.4 | ✅ |
| itsc | t2 | noload | 1200.0 | fft | 80.0 | 79.833 | 0.1666 | 1700.1 | ✅ |
| itsc | t5 | noload | 1200.0 | fft | 120.0 | 120.0 | 0.0 | 13652.0 | ✅ |
| itsc | t5 | noload | 1200.0 | fft | 40.0 | 40.167 | 0.1667 | 4243.6 | ✅ |
| itsc | t5 | noload | 1200.0 | fft | 80.0 | 79.833 | 0.1667 | 4042.5 | ✅ |
| itsc | t10 | noload | 1200.0 | fft | 120.0 | 120.0 | 0.0 | 24657.5 | ✅ |
| itsc | t10 | noload | 1200.0 | fft | 40.0 | 40.167 | 0.1667 | 7588.6 | ✅ |
| itsc | t10 | noload | 1200.0 | fft | 80.0 | 79.833 | 0.1667 | 7726.7 | ✅ |
| itsc | t2 | rated | 1170.7 | fft | 120.0 | 120.0 | 0.0 | 16749.6 | ✅ |
| itsc | t2 | rated | 1170.7 | fft | 40.488 | 40.333 | 0.1549 | 4166.4 | ✅ |
| itsc | t2 | rated | 1170.7 | fft | 79.512 | 79.667 | 0.1549 | 4017.3 | ✅ |
| itsc | t5 | rated | 1170.7 | fft | 120.0 | 120.0 | 0.0 | 41003.0 | ✅ |
| itsc | t5 | rated | 1170.7 | fft | 40.488 | 40.333 | 0.1549 | 8681.5 | ✅ |
| itsc | t5 | rated | 1170.7 | fft | 79.512 | 79.667 | 0.1549 | 8588.0 | ✅ |
| itsc | t10 | rated | 1170.7 | fft | 120.0 | 120.0 | 0.0 | 67912.0 | ✅ |
| itsc | t10 | rated | 1170.7 | fft | 40.488 | 40.333 | 0.1549 | 11463.2 | ✅ |
| itsc | t10 | rated | 1170.7 | fft | 79.512 | 79.667 | 0.1549 | 12926.4 | ✅ |
| bpfo | incipient | noload | 1200.02 | envelope | 61.416 | 61.5 | 0.0843 | 207.3 | ✅ |
| bpfo | incipient | noload | 1200.02 | envelope | 122.831 | 122.833 | 0.0019 | 115.4 | ✅ |
| bpfo | moderate | noload | 1200.03 | envelope | 61.416 | 61.5 | 0.0838 | 243.4 | ✅ |
| bpfo | moderate | noload | 1200.03 | envelope | 122.832 | 122.833 | 0.001 | 130.9 | ✅ |
| bpfo | severe | noload | 1200.05 | envelope | 61.417 | 61.5 | 0.0826 | 246.0 | ✅ |
| bpfo | severe | noload | 1200.05 | envelope | 122.835 | 122.833 | 0.0015 | 128.8 | ✅ |
| bpfo | incipient | rated | 1170.71 | envelope | 59.916 | 60.0 | 0.0844 | 266.9 | ✅ |
| bpfo | incipient | rated | 1170.71 | envelope | 119.831 | 119.833 | 0.0021 | 142.6 | ✅ |
| bpfo | moderate | rated | 1170.72 | envelope | 59.916 | 60.0 | 0.0837 | 269.3 | ✅ |
| bpfo | moderate | rated | 1170.72 | envelope | 119.833 | 119.833 | 0.0007 | 147.6 | ✅ |
| bpfo | severe | rated | 1170.76 | envelope | 59.918 | 60.0 | 0.082 | 287.8 | ✅ |
| bpfo | severe | rated | 1170.76 | envelope | 119.836 | 119.833 | 0.0027 | 145.2 | ✅ |
| bpfi | incipient | noload | 1200.02 | envelope | 98.587 | 98.667 | 0.0794 | 134.3 | ✅ |
| bpfi | incipient | noload | 1200.02 | envelope | 78.587 | 78.667 | 0.0798 | 72.4 | ✅ |
| bpfi | incipient | noload | 1200.02 | envelope | 118.588 | 118.5 | 0.0876 | 79.8 | ✅ |
| bpfi | moderate | noload | 1200.04 | envelope | 98.588 | 98.667 | 0.0784 | 137.9 | ✅ |
| bpfi | moderate | noload | 1200.04 | envelope | 78.588 | 78.667 | 0.079 | 78.3 | ✅ |
| bpfi | moderate | noload | 1200.04 | envelope | 118.589 | 118.5 | 0.0889 | 81.4 | ✅ |
| bpfi | severe | noload | 1200.08 | envelope | 98.592 | 98.667 | 0.0746 | 139.2 | ✅ |
| bpfi | severe | noload | 1200.08 | envelope | 78.591 | 78.667 | 0.076 | 77.9 | ✅ |
| bpfi | severe | noload | 1200.08 | envelope | 118.593 | 118.5 | 0.0934 | 84.4 | ✅ |
| bpfi | incipient | rated | 1170.71 | envelope | 96.179 | 96.167 | 0.0128 | 137.0 | ✅ |
| bpfi | incipient | rated | 1170.71 | envelope | 76.668 | 76.667 | 0.0008 | 84.6 | ✅ |
| bpfi | incipient | rated | 1170.71 | envelope | 115.691 | 115.833 | 0.142 | 89.9 | ✅ |
| bpfi | moderate | rated | 1170.74 | envelope | 96.181 | 96.167 | 0.0146 | 140.6 | ✅ |
| bpfi | moderate | rated | 1170.74 | envelope | 76.669 | 76.667 | 0.0024 | 84.4 | ✅ |
| bpfi | moderate | rated | 1170.74 | envelope | 115.694 | 115.833 | 0.1397 | 89.0 | ✅ |
| bpfi | severe | rated | 1170.79 | envelope | 96.186 | 96.167 | 0.019 | 150.9 | ✅ |
| bpfi | severe | rated | 1170.79 | envelope | 76.672 | 76.667 | 0.0058 | 90.3 | ✅ |
| bpfi | severe | rated | 1170.79 | envelope | 115.699 | 115.833 | 0.1345 | 92.4 | ✅ |
| unbalance | G6.3 | noload | 1200.0 | fft | 20.0 | 19.833 | 0.1667 | 1478.1 | ✅ |
| unbalance | G16 | noload | 1200.0 | fft | 20.0 | 19.833 | 0.1667 | 7681.5 | ✅ |
| unbalance | G40 | noload | 1200.0 | fft | 20.0 | 19.833 | 0.1667 | 20648.8 | ✅ |
| unbalance | G6.3 | rated | 1170.7 | fft | 19.512 | 19.667 | 0.1549 | 3393.1 | ✅ |
| unbalance | G16 | rated | 1170.7 | fft | 19.512 | 19.667 | 0.1549 | 7343.2 | ✅ |
| unbalance | G40 | rated | 1170.7 | fft | 19.512 | 19.667 | 0.155 | 7770.7 | ✅ |

**결과: 81/81 통과 (판정 제외 3건: 이론 주파수 < 2Δf), 전체 판정 = PASS**

판정 제외 근거: 무부하(≈동기속도) 조건에서는 슬립 s≈0 이므로 회전자 바 파손의 2sf 성분이 0 Hz로 수렴 — 실제 모터에서도 무부하 MCSA로는 BRB를 검출할 수 없다(부하 시험 필요)는 문헌 결론과 일치.