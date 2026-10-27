# -*- coding: utf-8 -*-
"""fault_control_window.py — 아이작심 안의 "VIGENT 전기 결함 조작" 패널 (Q1, 2026-10-27). omni.ui, GUI 전용.

모드 선택은 없다(전기 전용). 결함 변수 4개(결함 상/코일 · 단락 턴수 · 접촉 저항 · 전압 불평형)를 USD 속성(/World/VigentFaultController)에 쓰고,
메인 루프의 ManualFaultController.poll() 이 2 Hz 로 읽어 시나리오와 같은 주입 경로로 엔진 케이스를 바꾼다 (app/fault_controller.py).
실시간 판정 프레임은 엔진 state 값을 그대로 보여준다(0.5 s). 한글은 ui/ko_text.KoLabel(PIL 비트맵 PNG → ui.Image) 로 — omni.ui 글리프 한계(실측) 때문에
버튼·콤보박스 **안의** 글자는 ASCII 이고 그 옆·위의 설명은 한글이다. 창 제목도 Kit 폰트라 ASCII.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ui.ko_text import KoLabel, ko_png  # noqa: E402
from viz.view_mode import PANEL_MAP  # noqa: E402  (버튼 라벨 ↔ 모드 매핑의 단일 출처)

WHITE = (232, 236, 241, 255)
GRAY = (150, 158, 168, 255)
DIM = (110, 118, 128, 255)
ORANGE = (255, 115, 26, 255)
GREEN = (38, 242, 89, 255)
RED = (255, 20, 13, 255)
CYAN = (102, 221, 255, 255)
LEVEL_RGBA = {"SAFE": GREEN, "WARN": ORANGE, "DANGER": RED}
LEVEL_KO = {"SAFE": "안전", "WARN": "경고", "DANGER": "위험"}
VIEWS = [(m, ko) for ko, m in PANEL_MAP.items()]    # 반투명 = half_translucent · 절단 = cutaway · 권선만 = windings_only
STREAM_SIZES = [(1280, 720), (960, 540)]


class FaultControlWindow:
    def __init__(self, state, ctrl, phase_labels: dict, m1=None, view=None, streamer=None, bridge=None, log=print,
                 title: str = "VIGENT - Electrical Fault Control", width: int = 400, height: int = 820, pos=(20, 60), show_notice: bool = True):
        import omni.ui as ui
        self.ui, self.state, self.ctrl, self.m1, self.streamer, self.log = ui, state, ctrl, m1, streamer, log
        self.view, self.bridge = view, bridge          # view: viz/view_mode.ViewMode (뷰 전환 유일 진입점), bridge: 8765 LiveBridge (데이터 클라이언트 수)
        self.phase_labels = dict(phase_labels)
        self.immediate = True
        self._syncing = False
        self._last_update = 0.0
        self.window = ui.Window(title, width=width, height=height)
        try:
            self.window.position_x, self.window.position_y = pos
        except Exception:  # noqa: BLE001
            pass
        # 콤보 항목: 상 × 첫 코일 (USD 에 있는 코일 이름 — 하드코딩 없음). 내부 키 A|B|C, 표시는 config phase_labels (R·S·T)
        self.phase_items = []
        for p in ("A", "B", "C"):
            coils = ctrl.phase_coils.get(p) or []
            if coils:
                self.phase_items.append((p, coils[0]))
        if not self.phase_items:
            self.phase_items = [("A", "Coil_01")]
        self.rf_items = [f"{v:g}" + (" (metal)" if abs(v - 0.1) < 1e-9 else "") for v in ctrl.rf_values]
        self._build(show_notice)

    # ------------------------------------------------------------------ 구성
    def _build(self, show_notice: bool) -> None:
        ui = self.ui
        S = lambda n, c=0xFFFFFFFF: {"font_size": n, "color": c}  # noqa: E731
        with self.window.frame:
            with ui.ScrollingFrame(horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF):
                with ui.VStack(spacing=6):   # 주의: style margin 을 주면 ui.Image(한글 비트맵)가 축소된다(실측) — 여백은 Spacer 로
                    with ui.HStack(height=26):
                        KoLabel(ui, "VIGENT 전기 결함 조작", px=17, color=CYAN, bold=True)
                        ui.Spacer()
                        self._live_dot = ui.Circle(radius=6, width=16, height=16, style={"background_color": 0xFF666666})
                        self._live_lbl = KoLabel(ui, "데이터 0 · 화면 0", px=13, color=GRAY)
                    if show_notice:
                        KoLabel(ui, "모드 항목 삭제됨 — 전기 결함 고정", px=12, color=DIM)
                    ui.Separator(height=4)

                    # ---- 1. 결함 주입
                    with ui.CollapsableFrame("Fault injection", height=0):
                        with ui.VStack(spacing=6):
                            KoLabel(ui, "결함 주입", px=14, color=CYAN, bold=True)
                            with ui.HStack(height=24):
                                KoLabel(ui, "결함 상 / 코일", px=13, width=120)
                                self._phase_combo = ui.ComboBox(0, *[f"{self.phase_labels.get(p, p)} phase - {c}" for p, c in self.phase_items], height=22)
                                self._phase_combo.model.add_item_changed_fn(lambda *_: self._on_edit())
                            with ui.HStack(height=24):
                                KoLabel(ui, "단락 턴수", px=13, width=120)
                                self._turns_model = ui.SimpleIntModel(0)                       # 명시 모델 — 시나리오 값 표시(set_value)가 위젯에 바로 그려지도록
                                self._turns = ui.IntSlider(self._turns_model, min=0, max=self.ctrl.max_turns, height=22)
                                self._turns.model.add_value_changed_fn(lambda m: (None if self._syncing else self._turns_lbl.set(f"{m.get_value_as_int()} / {self.ctrl.max_turns} 턴", WHITE)))
                                self._turns.model.add_end_edit_fn(lambda *_: self._on_edit())
                                self._turns_lbl = KoLabel(ui, f"0 / {self.ctrl.max_turns} 턴", px=13, width=130)
                            with ui.HStack(height=24):
                                KoLabel(ui, "접촉 저항 [Ω]", px=13, width=120)
                                idx0 = min(range(len(self.ctrl.rf_values)), key=lambda i: abs(self.ctrl.rf_values[i] - 0.1))
                                self._rf_combo = ui.ComboBox(idx0, *self.rf_items, height=22)
                                self._rf_combo.model.add_item_changed_fn(lambda *_: self._on_edit())
                            with ui.HStack(height=24):
                                KoLabel(ui, "전압 불평형", px=13, width=120)
                                self._unb_combo = ui.ComboBox(0, "none", "config case (fixed)", height=22)
                                self._unb_combo.model.add_item_changed_fn(lambda *_: self._on_edit())
                            KoLabel(ui, "가변 % 는 엔진 규칙이 없어 config 케이스 켜기/끄기만", px=11, color=DIM)
                            with ui.HStack(height=22):
                                cb = ui.CheckBox(width=22)
                                cb.model.set_value(True)
                                cb.model.add_value_changed_fn(lambda m: setattr(self, "immediate", m.get_value_as_bool()))
                                KoLabel(ui, "슬라이더를 놓으면 바로 적용", px=13)
                            with ui.HStack(height=34, spacing=8):
                                ui.Button("", image_url=ko_png("적용", 15, WHITE, bold=True), image_width=60, image_height=22, clicked_fn=self.apply,
                                          style={"background_color": 0xFF1A73FF, "border_radius": 6})
                                ui.Button("", image_url=ko_png("정상으로", 15, WHITE), image_width=80, image_height=22, clicked_fn=self.reset_to_healthy,
                                          style={"background_color": 0xFF555555, "border_radius": 6})
                            self._status = KoLabel(ui, "준비", px=12, color=GRAY)

                    # ---- 2. 실시간 판정 (읽기 전용)
                    with ui.CollapsableFrame("Live judgment (read-only)", height=0):
                        with ui.VStack(spacing=4):
                            KoLabel(ui, "실시간 판정 (읽기 전용) — 엔진 state 값, 0.5 s 갱신", px=13, color=CYAN, bold=True)
                            self._r = {}
                            for key, name in (("i2i1", "전류 불균형 I₂/I₁"), ("i_f", "단락 전류 I_f [A]"), ("p_loop", "발열 P_loop [W]"),
                                              ("status", "판정"), ("persist", "지속 카운터"), ("load", "운전 부하"), ("source", "조작 주체")):
                                with ui.HStack(height=22):
                                    KoLabel(ui, name, px=13, width=150, color=GRAY)
                                    self._r[key] = KoLabel(ui, "—", px=14, bold=(key == "status"))
                            self._foot = KoLabel(ui, "해석표(LUT v2) 기준 · 대시보드로 송신 중 (0 클라이언트)", px=11, color=DIM)

                    # ---- 3. 보기
                    with ui.CollapsableFrame("View", height=0):
                        with ui.VStack(spacing=4):
                            KoLabel(ui, "보기", px=13, color=CYAN, bold=True)
                            with ui.HStack(height=30, spacing=6):
                                self._view_btns = {}
                                for key, ko in VIEWS:
                                    b = ui.Button("", image_url=ko_png(ko, 14, WHITE), image_width=56, image_height=20, clicked_fn=lambda k=key: self.set_view(k))
                                    self._view_btns[key] = b
                            self._refresh_view_buttons()

                    # ---- 4. 화면 송출 설정 (접힘)
                    with ui.CollapsableFrame("Stream settings", height=0, collapsed=True):
                        with ui.VStack(spacing=4):
                            KoLabel(ui, "화면 송출 설정 (런타임만, config 에 쓰지 않음)", px=13, color=CYAN, bold=True)
                            port = getattr(self.streamer, "port", None)
                            with ui.HStack(height=22):
                                KoLabel(ui, "포트 (읽기 전용)", px=13, width=130, color=GRAY)
                                ui.Label(f"{port if port else '-'}  (127.0.0.1)", style=S(13))
                            with ui.HStack(height=22):
                                KoLabel(ui, "해상도", px=13, width=130, color=GRAY)
                                cur = tuple(getattr(self.streamer, "size", (1280, 720)) or (1280, 720))
                                idx = STREAM_SIZES.index(cur) if cur in STREAM_SIZES else 0
                                self._res_combo = ui.ComboBox(idx, *[f"{w}x{h}" for w, h in STREAM_SIZES], height=22)
                                self._res_combo.model.add_item_changed_fn(lambda *_: self._on_stream_changed())
                            with ui.HStack(height=22):
                                KoLabel(ui, "JPEG 품질", px=13, width=130, color=GRAY)
                                self._q = ui.IntSlider(min=60, max=90, height=20)
                                self._q.model.set_value(int(getattr(self.streamer, "quality", 80) or 80))
                                self._q.model.add_end_edit_fn(lambda *_: self._on_stream_changed())
                    ui.Spacer(height=4)
                    KoLabel(ui, "시뮬레이션 추정값 (실측 아님)", px=11, color=(85, 255, 85, 255))

    # ------------------------------------------------------------------ 값 읽기/쓰기
    def _widget_spec(self) -> dict:
        pi = self._phase_combo.model.get_item_value_model().get_value_as_int()
        p, coil = self.phase_items[max(0, min(pi, len(self.phase_items) - 1))]
        ri = self._rf_combo.model.get_item_value_model().get_value_as_int()
        rf = self.ctrl.rf_values[max(0, min(ri, len(self.ctrl.rf_values) - 1))]
        unb = 1.0 if self._unb_combo.model.get_item_value_model().get_value_as_int() == 1 else 0.0
        return {"phase": p, "coil": coil, "turns": int(self._turns.model.get_value_as_int()), "R_f_ohm": float(rf), "unbalance": unb}

    def _on_edit(self) -> None:
        if self._syncing:
            return
        if self.immediate:
            self.apply()
        else:
            self.set_status("변경됨 — [적용] 을 누르세요", ORANGE)

    def apply(self) -> None:
        spec = self._widget_spec()
        self.ctrl.write(**spec)
        self.set_status(f"적용 요청: {self.phase_labels.get(spec['phase'], spec['phase'])}상 {spec['coil']} · {spec['turns']}턴 · R_f {spec['R_f_ohm']:g} Ω" + (" · 불평형" if spec["unbalance"] > 0 else ""), WHITE)

    def reset_to_healthy(self) -> None:
        self._syncing = True
        try:
            self._turns.model.set_value(0)
            self._unb_combo.model.get_item_value_model().set_value(0)
        finally:
            self._syncing = False
        self.ctrl.write(turns=0, unbalance=0.0)
        self.set_status("정상으로 (턴 0 · 불평형 0 · 지속 카운터 리셋)", GREEN)

    def set_view(self, key: str) -> None:
        """보기 버튼: 유일 진입점 ViewMode.set(source="manual"). 버튼 색은 클릭이 아니라 USD readback 결과로 (실패하면 회색 + 경고)."""
        actual = None
        if self.view is not None:
            try:
                actual = self.view.set(key, "manual")
            except Exception as e:  # noqa: BLE001
                self.log(f"[panel] set_view {key}: {e}")
        elif self.m1 is not None:
            self.m1.set_view(key); actual = getattr(self.m1, "view", None)
        if actual != key:
            self.log(f"[panel] WARNING view {key} not applied (usd={actual}) - {getattr(self.view, 'last_error', '')}")
        self._refresh_view_buttons()

    def _refresh_view_buttons(self, cur: str | None = None) -> None:
        cur = cur or (self.view.readback() if self.view is not None else getattr(self.m1, "view", None))
        for k, b in self._view_btns.items():
            b.set_style({"background_color": 0xFF2D6A9F if k == cur else 0xFF3A3A3A, "border_radius": 6})

    def _on_stream_changed(self) -> None:
        if self.streamer is None:
            return
        i = self._res_combo.model.get_item_value_model().get_value_as_int()
        self.streamer.size = STREAM_SIZES[max(0, min(i, len(STREAM_SIZES) - 1))]
        self.streamer.quality = int(self._q.model.get_value_as_int())
        self.log(f"[panel] stream {self.streamer.size[0]}x{self.streamer.size[1]} q{self.streamer.quality} (runtime only)")

    # ------------------------------------------------------------------ 외부 갱신
    def set_status(self, text: str, color=GRAY) -> None:
        self._status.set(text, color)

    def sync_from_state(self) -> None:
        """시나리오·명령으로 바뀐 상태를 패널 위젯에 반영 (수동 사양만)."""
        m = self.state.manual
        self._syncing = True
        try:
            pi = next((i for i, (p, _) in enumerate(self.phase_items) if p == m.phase), 0)
            self._phase_combo.model.get_item_value_model().set_value(pi)
            # 시나리오가 결함을 쥔 동안은 슬라이더를 수동 사양(0)으로 되돌리지 않는다 — update_readings 가 장면 주입값을 읽기 전용으로 보여준다
            if self.state.control_source == "manual" and self._turns.model.get_value_as_int() != int(m.turns):
                self._turns.model.set_value(int(m.turns))
            ri = min(range(len(self.ctrl.rf_values)), key=lambda i: abs(self.ctrl.rf_values[i] - m.R_f_ohm))
            self._rf_combo.model.get_item_value_model().set_value(ri)
            self._unb_combo.model.get_item_value_model().set_value(1 if m.unbalance > 0 else 0)
        finally:
            self._syncing = False

    def update_readings(self, st: dict | None, persist: dict | None, clients: int, data_clients: int | None = None, now: float | None = None) -> None:
        """엔진 state_dict 그대로 표시 (0.5 s). persist = {"pending_s", "need_s"} (Judge 지속 시계). clients = 8766 화면 송출, data_clients = 8765 데이터."""
        now = now if now is not None else time.perf_counter()
        if now - self._last_update < 0.5:
            return
        self._last_update = now
        if data_clients is None:
            data_clients = getattr(getattr(self, "bridge", None), "clients", 0) or 0
        live = data_clients >= 1
        self._live_dot.set_style({"background_color": 0xFF59F226 if live else 0xFF666666})
        self._live_lbl.set(f"데이터 {data_clients} · 화면 {clients}", GREEN if live else GRAY)
        self._refresh_view_buttons()                       # 버튼 색 = 실제 USD 선택값 (시나리오·cam_plan 이 바꿔도 따라온다)
        if not st:
            return
        # 시나리오 모드: 슬라이더에 현재 장면의 주입값을 읽기 전용으로 보여준다 (건드리면 manual - 기존 동작)
        if st.get("control_source", "scenario") != "manual":
            es = st.get("electrical_source") or {}
            sc_turns = int(round(float(es.get("turns") or 0))) if es.get("case_method") == "lut" else 0
            self._syncing = True
            try:
                if self._turns.model.get_value_as_int() != sc_turns:
                    self._turns.model.set_value(int(sc_turns))
                self._turns_lbl.set(f"{sc_turns} / {self.ctrl.max_turns} 턴 (시나리오)", GRAY)
            finally:
                self._syncing = False
        else:
            self._turns_lbl.set(f"{self._turns.model.get_value_as_int()} / {self.ctrl.max_turns} 턴", WHITE)
        es = st.get("electrical_source") or {}
        self._r["i2i1"].set(f"{st.get('i2_over_i1', 0):.4f}")
        i_f = es.get("i_f_A")
        self._r["i_f"].set("—" if i_f is None else f"{float(i_f):.1f} A")
        self._r["p_loop"].set(f"{float(st.get('p_loop_total_W') or 0):.0f} W")
        lv = (st.get("status") or {}).get("status", "SAFE")
        cause = (st.get("status") or {}).get("cause_signal", "-")
        self._r["status"].set(f"{LEVEL_KO.get(lv, lv)}" + (f" · 원인 {cause}" if cause and cause != "-" else ""), LEVEL_RGBA.get(lv, WHITE))
        if persist:
            self._r["persist"].set(f"{float(persist.get('pending_s') or 0):.1f} / {float(persist.get('need_s') or 0):.1f} s")
        self._r["load"].set(f"{float(st.get('load', 0)) * 100:.0f} %")
        src = st.get("control_source", "scenario")
        self._r["source"].set("수동 (패널)" if src == "manual" else "시나리오", ORANGE if src == "manual" else WHITE)
        self._foot.set(f"해석표(LUT v2) 기준 · 대시보드로 송신 중 ({clients} 클라이언트)")
