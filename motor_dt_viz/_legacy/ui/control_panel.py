# -*- coding: utf-8 -*-
"""control_panel.py — 발표용 제어 패널 (omni.ui). GUI 모드 전용.

CLAUDE.md §7:
  · 모드 선택 [기계적 결함] [전기적 결함] [통합]
  · 슬라이더: 부하율(0~150 %), 시간 배속, 슬로모션 배속
  · 결함 주입 토글 8종
  · 버튼 [리셋] [시나리오 자동 재생]

⚠️ omni.ui 기본 폰트에 한글 글리프가 없어 라벨은 영문으로 표기한다 (Phase 3 실측).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.config_loader import load

MODES = ("mechanical", "electrical", "integrated")
MODE_LABEL = {"mechanical": "Mechanical only", "electrical": "Electrical only",
              "integrated": "Integrated"}
# 예전 설정 파일이 쓰던 이름을 받아준다
MODE_ALIAS = {"thermal": "mechanical"}


def normalize_mode(mode: str) -> str:
    return MODE_ALIAS.get(mode, mode)

# 열 결함 토글 (config/thermal.yaml faults 키)
THERMAL_FAULTS = [
    ("bearing_de_fault", "DE bearing fault"),
    ("bearing_nde_fault", "NDE bearing fault"),
    ("misalignment", "Shaft misalignment"),
    ("fan_failure", "Cooling fan failure"),
    ("brake_drag", "Brake drag"),
    ("overload", "Overload"),
]
# 전기 케이스 (config/electrical.yaml cases 키)
ELECTRICAL_CASES = [
    ("healthy", "Healthy"),
    ("itsc_4turn", "Inter-turn short 4T"),
    ("itsc_12turn", "Inter-turn short 12T"),
    ("voltage_unbalance", "Voltage unbalance"),
    ("single_phasing", "Single phasing"),
    ("no_load", "No load"),
    ("overload", "Overload 135%"),
]


@dataclass
class DemoState:
    """패널과 메인 루프가 공유하는 상태."""
    mode: str = "integrated"
    load: float = 1.0
    time_scale: float = 120.0
    slowmo: float = 1.0 / 60.0
    thermal_faults: list[str] = field(default_factory=list)
    electrical_case: str = "healthy"
    playing_scenario: bool = False
    request_reset: bool = False
    request_play: bool = False
    request_mode_reset: bool = False     # 모드 전환 — 머티리얼·입자·HUD 잔상 제거
    highlight_short_loop: bool = False
    housing_opacity: float = 0.68
    dirty: bool = True                  # 패널 조작이 있었음 → 루프가 반영

    def snapshot(self) -> dict:
        return {"mode": self.mode, "load": self.load, "time_scale": self.time_scale,
                "faults": list(self.thermal_faults), "case": self.electrical_case,
                "scenario": self.playing_scenario}


class ControlPanel:
    """omni.ui 창. 콜백이 DemoState 를 갱신하고, 메인 루프가 그것을 읽는다."""

    def __init__(self, state: DemoState, title: str = "VIGENT - Control",
                 width: int = 360, height: int = 640, pos=(20, 60)):
        import omni.ui as ui
        self.ui = ui
        self.state = state
        self.cfg_scn = load("scenario")
        self.window = ui.Window(title, width=width, height=height)
        try:
            self.window.position_x, self.window.position_y = pos
        except Exception:
            pass
        self._mode_buttons: dict[str, object] = {}
        self._fault_models: dict[str, object] = {}
        self._build()

    # ------------------------------------------------------------------ 구성
    def _build(self) -> None:
        ui = self.ui
        S = lambda n, c=0xFFFFFFFF: {"font_size": n, "color": c}  # noqa: E731
        with self.window.frame:
            with ui.VStack(spacing=6, style={"margin": 8}):
                ui.Label("MODE", style=S(15, 0xFF66DDFF))
                with ui.HStack(height=28, spacing=4):
                    for m in MODES:
                        b = ui.Button(MODE_LABEL[m], clicked_fn=lambda m=m: self._set_mode(m))
                        self._mode_buttons[m] = b
                self._mode_label = ui.Label("", height=18, style=S(13, 0xFFAAAAAA))
                ui.Separator(height=6)

                ui.Label("LOAD / SPEED", style=S(15, 0xFF66DDFF))
                self._load_model = self._slider("Load  [%]", 0.0, 150.0, self.state.load * 100,
                                                lambda v: self._set_load(v / 100.0))
                self._ts_model = self._slider("Time scale  [x]", 1.0, 600.0, self.state.time_scale,
                                              self._set_time_scale)
                self._sm_model = self._slider("Slow motion  1/x", 1.0, 240.0, 1.0 / self.state.slowmo,
                                              lambda v: self._set_slowmo(1.0 / max(v, 1.0)))
                ui.Separator(height=6)

                # 기계 결함 토글 — 전기 전용 모드에서는 통째로 숨긴다
                self._sec_mech = ui.VStack(spacing=4)
                with self._sec_mech:
                    ui.Label("MECHANICAL FAULTS", style=S(15, 0xFF66DDFF))
                    for key, label in THERMAL_FAULTS:
                        with ui.HStack(height=22):
                            cb = ui.CheckBox(width=22)
                            cb.model.add_value_changed_fn(
                                lambda m, k=key: self._toggle_fault(k, m.get_value_as_bool()))
                            self._fault_models[key] = cb.model
                            ui.Label(label, style=S(13))
                    ui.Separator(height=6)

                # 전기 케이스 — 기계 전용 모드에서는 통째로 숨긴다
                self._sec_elec = ui.VStack(spacing=4)
                with self._sec_elec:
                    ui.Label("ELECTRICAL CASE", style=S(15, 0xFF66DDFF))
                    self._case_combo = ui.ComboBox(0, *[l for _, l in ELECTRICAL_CASES], height=24)
                    self._case_combo.model.add_item_changed_fn(self._on_case_changed)
                    ui.Separator(height=6)

                ui.Label("VIEW", style=S(15, 0xFF66DDFF))
                with ui.HStack(height=22):
                    cb = ui.CheckBox(width=22)
                    cb.model.add_value_changed_fn(
                        lambda m: self._set_highlight(m.get_value_as_bool()))
                    ui.Label("Highlight short-turn loop (x-ray)", style=S(13))
                ui.Separator(height=8)

                with ui.HStack(height=34, spacing=6):
                    ui.Button("RESET", clicked_fn=self._reset)
                    ui.Button("AUTO-PLAY SCENARIO", clicked_fn=self._play)
                self._status = ui.Label("Ready", height=20, style=S(13, 0xFF88FF88))
                ui.Spacer()
                ui.Label("Simulation-based estimate (not measured)", style=S(12, 0xFF55FF55))
        self._refresh_mode_buttons()

    def _slider(self, label: str, lo: float, hi: float, value: float, on_change):
        ui = self.ui
        with ui.HStack(height=24):
            ui.Label(label, width=120, style={"font_size": 13})
            sl = ui.FloatSlider(min=lo, max=hi, step=(hi - lo) / 200.0)
            sl.model.set_value(float(value))
            sl.model.add_value_changed_fn(lambda m: on_change(m.get_value_as_float()))
        return sl.model

    # ------------------------------------------------------------------ 콜백
    def _set_mode(self, mode: str) -> None:
        if mode == self.state.mode:
            return
        self.state.mode = mode
        self.state.dirty = True
        # 이전 모드의 머티리얼·입자·HUD 잔상이 남지 않도록 루프에 리셋을 요청한다
        self.state.request_mode_reset = True
        # 모드를 바꾸면 그 모드와 무관한 결함은 해제한다
        if mode == "electrical":
            self.state.thermal_faults.clear()
            for m in self._fault_models.values():
                m.set_value(False)
        elif mode == "mechanical":
            self.state.electrical_case = "healthy"
            self._case_combo.model.get_item_value_model().set_value(0)
        self._refresh_mode_buttons()

    def _refresh_mode_buttons(self) -> None:
        mode = self.state.mode
        for m, b in self._mode_buttons.items():
            b.set_style({"background_color": 0xFF2D6A9F if m == mode else 0xFF3A3A3A,
                         "color": 0xFFFFFFFF})
        self._mode_label.text = f"current: {MODE_LABEL.get(mode, mode)}"
        # 다른 결함 유형의 조작부는 감춰 한 화면에 한 가지만 보이게 한다
        self._sec_mech.visible = mode in ("mechanical", "integrated")
        self._sec_elec.visible = mode in ("electrical", "integrated")

    def _set_load(self, v: float) -> None:
        self.state.load = max(0.0, min(v, 1.5))
        self.state.dirty = True

    def _set_time_scale(self, v: float) -> None:
        self.state.time_scale = max(1.0, v)
        self.state.dirty = True

    def _set_slowmo(self, v: float) -> None:
        self.state.slowmo = v
        self.state.dirty = True

    def _toggle_fault(self, key: str, on: bool) -> None:
        if on and key not in self.state.thermal_faults:
            self.state.thermal_faults.append(key)
        elif not on and key in self.state.thermal_faults:
            self.state.thermal_faults.remove(key)
        self.state.dirty = True

    def _on_case_changed(self, model, item) -> None:
        idx = model.get_item_value_model().get_value_as_int()
        self.state.electrical_case = ELECTRICAL_CASES[idx][0]
        self.state.dirty = True

    def _set_highlight(self, on: bool) -> None:
        self.state.highlight_short_loop = on
        self.state.dirty = True

    def _reset(self) -> None:
        self.state.request_reset = True
        self.state.playing_scenario = False
        self.state.thermal_faults.clear()
        self.state.electrical_case = "healthy"
        for m in self._fault_models.values():
            m.set_value(False)
        self._case_combo.model.get_item_value_model().set_value(0)
        self.set_status("Reset")

    def _play(self) -> None:
        self.state.request_play = True
        self.set_status("Auto-play started")

    # ------------------------------------------------------------------ 외부 갱신
    def set_status(self, text: str, color: int = 0xFF88FF88) -> None:
        self._status.text = text
        self._status.style = {"font_size": 13, "color": color}

    def sync_from_state(self) -> None:
        """시나리오 재생 중 상태가 코드로 바뀐 것을 패널에 반영한다."""
        for key, model in self._fault_models.items():
            want = key in self.state.thermal_faults
            if model.get_value_as_bool() != want:
                model.set_value(want)
        idx = next((i for i, (k, _) in enumerate(ELECTRICAL_CASES)
                    if k == self.state.electrical_case), 0)
        vm = self._case_combo.model.get_item_value_model()
        if vm.get_value_as_int() != idx:
            vm.set_value(idx)
        self._refresh_mode_buttons()
