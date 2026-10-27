# -*- coding: utf-8 -*-
"""live_signals.py — 라이브 state 에 덧붙이는 전류 성분·파형 필드 (TASK 레이아웃 A §A1, 2026-10-27).

dashboard/tools/export_status_data.py 의 case_signals() 와 **같은 식**(engine.CurrentModel._phasors → symmetrical_components, CurrentModel.waveform)으로
케이스별 I₁·I₂·I₀ [A RMS] 와 최근 2주기 파형(2 kHz, 위상 0 기준)을 만든다. 값은 케이스에만 의존하므로 케이스별로 한 번 계산해 캐시한다(메인 루프 비용 0).
엔진 수치·판정은 건드리지 않는다. tests/test_live_signals.py 가 export 쪽 함수와 같은 값인지 대조한다.
"""
from __future__ import annotations

import numpy as np

from engine.current_model import CurrentModel, symmetrical_components

FS_HZ = 2000.0
CYCLES = 2


def case_signal(cm: CurrentModel, case: str, fs_hz: float = FS_HZ, cycles: int = CYCLES) -> dict | None:
    """{"sym_components_A": {i1_A, i2_A, i0_A}, "waveform_last_2cycles": {fs_Hz, f0_Hz, cycles, unit, t_ms, A, B, C}} 또는 모르는 케이스면 None."""
    if case not in cm.cases:
        return None
    i_rated = cm.motor.rated_current("rated_line_A")
    ph = cm._phasors(case, i_rated)
    i1, i2, i0 = symmetrical_components(*[complex(x) for x in ph])
    t = np.arange(0, cycles / cm.f0, 1.0 / fs_hz)
    w = np.asarray(cm.waveform(t, case, "rated_line_A"), dtype=float)
    if w.shape[0] != 3:
        w = w.T
    return {"sym_components_A": {"i1_A": round(abs(i1) / 2 ** 0.5, 4), "i2_A": round(abs(i2) / 2 ** 0.5, 4), "i0_A": round(abs(i0) / 2 ** 0.5, 4)},
            "waveform_last_2cycles": {"fs_Hz": fs_hz, "f0_Hz": float(cm.f0), "cycles": cycles, "unit": "A",
                                      "t_ms": [round(float(x) * 1000, 3) for x in t],
                                      "A": [round(float(x), 4) for x in w[0]], "B": [round(float(x), 4) for x in w[1]], "C": [round(float(x), 4) for x in w[2]]}}


class CaseSignalCache:
    def __init__(self, cm: CurrentModel):
        self.cm = cm
        self._cache: dict[str, dict | None] = {}

    def get(self, case: str) -> dict | None:
        if case not in self._cache:
            try:
                self._cache[case] = case_signal(self.cm, case)
            except Exception:  # noqa: BLE001
                self._cache[case] = None
        return self._cache[case]

    def invalidate(self) -> None:
        self._cache.clear()
