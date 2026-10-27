# -*- coding: utf-8 -*-
"""fault_controller.py — 패널 Q1 수동 결함 경로 (2026-10-27):

  패널 위젯 → /World/VigentFaultController 프림의 USD 속성(vigent:faultPhase · faultCoil · faultTurns · contactResistance · voltageUnbalance)
  → 매 프레임 poll(): 속성 읽기(2 Hz 제한, 마지막 값 보장) → 바뀌었으면 apply(): 시나리오가 쓰는 것과 같은 길로 엔진 케이스를 정한다
     (DemoState.electrical_case ← 런타임 등록 케이스 "manual_itsc" = electrical.yaml itsc_4turn 템플릿 복사 + lut {turns, R_f_ohm} — M1Model.register_runtime_case 와 같은 식)
  → 엔진(CurrentModel lut) → state → 코일 발광(M1Model.set_short_coil) · WebSocket 8765 · 스트림 8766.

계산식 추가 없음: 턴·R_f 는 LUT 격자 값만 허용하고 값은 LUT 가 보간한다. 전압 불평형은 config 의 voltage_unbalance 케이스(고정) 켜기/끄기뿐이다
(가변 % 는 phase_scale 을 새로 만드는 식이 필요해 금지 — 보고서 한계).
결함 상 B/C 는 엔진 파형의 상 순서를 돌리는 것(np.roll)으로 표현한다 — 새 수치 없음(대칭 성분 크기 불변). 코일 발광은 선택한 코일 프림에 단락 재질을 묶는다.
시작 시 속성은 정상(턴 0·불평형 0)으로 초기화한다 — USD 에 저장돼 있어도 다음 실행은 정상에서 시작.
"""
from __future__ import annotations

import time

from pxr import Sdf, UsdGeom

PRIM_PATH = "/World/VigentFaultController"
MANUAL_CASE = "manual_itsc"
UNBALANCE_CASE = "voltage_unbalance"
TEMPLATE_CASE = "itsc_4turn"
# (이름, 타입, 기본값, 문서)
ATTRS = [
    ("vigent:faultPhase", Sdf.ValueTypeNames.Token, "A", "결함 상 내부 키 A|B|C (표시 이름은 config electrical.yaml phase_labels: R·S·T)"),
    ("vigent:faultCoil", Sdf.ValueTypeNames.String, "Coil_01", "결함 코일 USD 프림 이름 (/World/M1/Stator/Coils/<name>, prim_map_M1.yaml 권선 그룹에서)"),
    ("vigent:faultTurns", Sdf.ValueTypeNames.Int, 0, "단락 턴수. 0 = 정상. 최대는 LUT 격자(turn_ratio_pct 최대 × N_ph)"),
    ("vigent:contactResistance", Sdf.ValueTypeNames.Float, 0.1, "접촉 저항 R_f [Ω] — LUT 격자 값만 (0.03/0.1/0.3/1.0)"),
    ("vigent:voltageUnbalance", Sdf.ValueTypeNames.Float, 0.0, "0 = 없음, >0 = config electrical.yaml voltage_unbalance 케이스(고정) 적용"),
]
PHASES = ("A", "B", "C")


def nearest(values, x: float) -> float:
    return float(min(values, key=lambda v: abs(float(v) - float(x))))


class ManualFaultController:
    def __init__(self, stage, cm, phase_coils: dict[str, list[str]], rate_hz: float = 2.0, log=print):
        self.stage, self.cm, self.log = stage, cm, log
        self.phase_coils = {p: list(v) for p, v in phase_coils.items() if v}
        self.rate_s = 1.0 / max(float(rate_hz), 0.1)
        lut = getattr(cm, "lut", None)
        self.rf_values = [float(x) for x in (lut.rfs if lut is not None else [0.1])]
        self.max_turns = int(round(float(lut.fracs[-1]) * lut.base_turns)) if lut is not None else 16
        self.prim = stage.GetPrimAtPath(PRIM_PATH)
        if not self.prim or not self.prim.IsValid():
            self.prim = UsdGeom.Xform.Define(stage, PRIM_PATH).GetPrim()
        self.attrs = {}
        for name, typ, default, doc in ATTRS:
            a = self.prim.GetAttribute(name)
            if not a or not a.IsValid():
                a = self.prim.CreateAttribute(name, typ, custom=True)
            try:
                a.SetDocumentation(doc)
            except Exception:  # noqa: BLE001
                pass
            a.Set(default)                       # 시작은 항상 정상
            self.attrs[name] = a
        self._applied: dict | None = None
        self._pending: dict | None = None
        self._applied = self.read()              # 시작 기준값(정상) — 첫 프레임에 '적용'으로 세지 않는다 (시나리오를 멈추지 않도록)
        self._last_apply_t = -1e9
        self._seq = 0
        self.stats = {"applied": 0, "coalesced": 0, "last_apply_wall": None, "last_latency_ms": None}

    # ------------------------------------------------------------------ 속성
    def read(self) -> dict:
        g = lambda k: self.attrs[k].Get()  # noqa: E731
        phase = str(g("vigent:faultPhase") or "A")
        if phase not in PHASES:
            phase = "A"
        coil = str(g("vigent:faultCoil") or (self.phase_coils.get(phase) or ["Coil_01"])[0])
        if coil not in (self.phase_coils.get(phase) or [coil]):
            coil = (self.phase_coils.get(phase) or [coil])[0]
        turns = max(0, min(int(g("vigent:faultTurns") or 0), self.max_turns))
        rf = nearest(self.rf_values, float(g("vigent:contactResistance") or self.rf_values[0]))
        unb = float(g("vigent:voltageUnbalance") or 0.0)
        return {"phase": phase, "coil": coil, "turns": turns, "R_f_ohm": rf, "unbalance": max(0.0, unb)}

    def write(self, **kw) -> None:
        """패널·테스트가 쓴다: 속성에 값을 쓴다 (적용은 poll 이 2 Hz 로)."""
        m = {"phase": "vigent:faultPhase", "coil": "vigent:faultCoil", "turns": "vigent:faultTurns", "R_f_ohm": "vigent:contactResistance", "unbalance": "vigent:voltageUnbalance"}
        for k, v in kw.items():
            if k in m and v is not None:
                self.attrs[m[k]].Set(v)
        self._write_wall = time.perf_counter()

    def write_healthy(self) -> None:
        self.write(turns=0, unbalance=0.0)

    # ------------------------------------------------------------------ 메인 루프
    def poll(self, now: float, force: bool = False) -> dict | None:
        """속성이 바뀌었고 2 Hz 간격이 지났으면 사양 dict 를 돌려준다(적용은 호출자가 apply). 마지막 값은 반드시 반영된다."""
        spec = self.read()
        if spec == self._applied and not force:
            self._pending = None
            return None
        if now - self._last_apply_t < self.rate_s and not force:
            if self._pending is not None and self._pending != spec:
                self.stats["coalesced"] += 1
            self._pending = spec
            return None
        self._pending = None
        self._last_apply_t = now
        return spec

    def apply(self, spec: dict, state, cm, player=None, case_cache=None) -> dict:
        """시나리오와 같은 길: DemoState.electrical_case(+load 유지) 를 정한다. 시나리오 재생 중이면 자동 정지 → 수동."""
        t0 = time.perf_counter()
        if state.playing_scenario:
            state.playing_scenario = False
            if player is not None:
                player.stop()
        if spec["turns"] > 0:
            tpl = dict(cm.cases[TEMPLATE_CASE])
            tpl["label"] = f"수동 턴간 단락 {spec['turns']}턴 (R_f {spec['R_f_ohm']:g} Ω)"
            tpl["lut"] = {"turns": int(spec["turns"]), "R_f_ohm": float(spec["R_f_ohm"])}
            tpl["load"] = float(state.load)
            tpl["target_i2i1"] = None
            if "short_loop" in tpl:
                tpl["short_loop"] = {**tpl["short_loop"], "turns": int(spec["turns"])}
            cm.cases[MANUAL_CASE] = tpl
            cm._lut_cache.pop(MANUAL_CASE, None)
            case = MANUAL_CASE
        elif spec["unbalance"] > 0:
            case = UNBALANCE_CASE
        else:
            case = "healthy"
        state.electrical_case = case
        state.fault_phase = spec["phase"] if case == MANUAL_CASE else "A"
        state.manual.phase, state.manual.coil, state.manual.turns = spec["phase"], spec["coil"], int(spec["turns"])
        state.manual.R_f_ohm, state.manual.unbalance = float(spec["R_f_ohm"]), float(spec["unbalance"])
        state.control_source = "manual"
        state.dirty = True
        if case_cache is not None:
            case_cache.invalidate()
        self._applied = dict(spec)
        self._seq += 1
        self.stats["applied"] += 1
        self.stats["last_apply_wall"] = time.time()
        self.stats["last_latency_ms"] = round((t0 - getattr(self, "_write_wall", t0)) * 1000, 1)
        self.log(f"[panel] apply #{self._seq}: {spec} -> case {case} (phase {state.fault_phase})")
        return {"case": case, "seq": self._seq, **spec}

    def mark_scenario(self, state) -> None:
        """대시보드 시나리오 ▾ (play_scenario) 가 결함을 다시 쥐면 수동 사양을 속성에서도 정상으로 되돌린다."""
        state.control_source = "scenario"
        state.fault_phase = "A"
        state.manual.turns = 0
        state.manual.unbalance = 0.0
        self.write_healthy()
        self._applied = self.read()
