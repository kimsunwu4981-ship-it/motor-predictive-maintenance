# -*- coding: utf-8 -*-
"""thresholds.py — VIGENT 상태 판정 엔진 (TASK_다중모터 §5). Isaac Sim 비의존.

세 단계 SAFE / WARN / DANGER. 규칙은 이 모듈에만, 숫자는 config/thresholds.yaml 과 모터 YAML(진동 규격)에만 있다.
애니메이션 HUD·대시보드 export·로그 판정이 모두 이 모듈을 쓴다.

  judge = Judge(motor=motor_library.load_motor("M3"))
  v = judge.update(t=12.0, signals={"temperature": {"bearing_de": 91.2, "winding": 80}, "current_ratio": {"A": 1.02},
                                     "i2i1": 0.006, "vibration": 3.6})
  v.status, v.cause_signal, v.cause_component, v.value, v.threshold  → "WARN", "temperature", "bearing_de", 91.2, "70~95 °C"

규칙:
  · 종합 상태 = 모든 신호 중 가장 나쁜 등급. 같은 등급이 여럿이면 임계 초과 정도(초과 비율)가 큰 것이 원인.
  · 히스테리시스: 등급 하향은 임계값의 hysteresis.fraction 만큼 안전 쪽으로 더 들어와야 바뀐다 (깜빡임 방지).
  · 지속 시간: 전류·진동·I₂/I₁·베어링 지표는 persistence_s 이상 계속돼야 등급이 오른다 (기동 돌입전류 무시).
    온도는 persistence 0 (느린 신호). 등급 하향에는 지속 조건을 두지 않는다 (히스테리시스가 맡는다).
  · 첫 호출(상태 없음)은 지속 조건 없이 현재값으로 판정한다 (로그 중간부터 판정을 시작해도 처음부터 맞게).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config_loader import load

LEVELS = ("SAFE", "WARN", "DANGER")
RANK = {lv: i for i, lv in enumerate(LEVELS)}
KINDS = ("temperature", "current_ratio", "i2i1", "vibration", "bearing_index")


@dataclass
class SignalVerdict:
    kind: str
    component: str          # 열 노드 키, 상(A/B/C), 또는 "-"
    value: float
    level: str              # 히스테리시스·지속 적용 후
    raw_level: str          # 현재값만의 등급
    threshold: str          # 사람이 읽는 경계 ("70~95 °C")
    exceed: float           # 임계 초과 비율 (원인 선정용, 0 이면 안전)
    note: str = ""          # 세부 라벨 (예: 20816-3 "정비 계획")


@dataclass
class Verdict:
    t: float
    status: str
    cause_signal: str
    cause_component: str
    value: float
    threshold: str
    signals: list[SignalVerdict] = field(default_factory=list)
    label_ko: str = ""
    icon: str = ""
    color: str = ""

    def as_dict(self) -> dict:
        return {"t": self.t, "status": self.status, "label": self.label_ko, "icon": self.icon, "color": self.color,
                "cause_signal": self.cause_signal, "cause_component": self.cause_component,
                "value": self.value, "threshold": self.threshold,
                "signals": [vars(s) for s in self.signals]}


class Judge:
    def __init__(self, cfg: dict | None = None, motor=None, vib_thresholds: dict | None = None):
        """motor: motor_library.Motor (진동 규격·정격 전류). vib_thresholds 로 직접 줄 수도 있다."""
        self.cfg = cfg or load("thresholds")
        self.motor = motor
        vt = vib_thresholds or (motor.vib_thresholds if motor is not None else None) or self.cfg["vibration"]["fallback"]
        self.vib = {k: float(vt[k]) for k in ("watch_mms", "plan_mms", "act_mms")}
        self.vib_standard = str(vt.get("standard", ""))
        self.hys = float(self.cfg["hysteresis"]["fraction"])
        self.persist = {k: float(v) for k, v in self.cfg["persistence_s"].items()}
        self._state: dict[tuple[str, str], str] = {}        # (kind, component) → 현재 등급
        self._since: dict[tuple[str, str], tuple[str, float]] = {}   # (kind, component) → (raw 등급, 그 등급이 시작된 t)
        self._last_t: float | None = None

    # ------------------------------------------------------------------ 경계 (상태 없음)
    def temp_bounds(self, component: str) -> dict:
        tc = self.cfg["temperature"]
        cls = tc["component_class"].get(component, "default")
        return tc[cls]

    def raw(self, kind: str, value: float, component: str = "-") -> tuple[str, str, float, str]:
        """현재값만으로 (등급, 경계 문자열, 초과 비율, 세부 라벨)."""
        c = self.cfg
        if kind == "temperature":
            b = self.temp_bounds(component)
            lo, hi = float(b["safe_below"]), float(b["danger_from"])
            lv = "SAFE" if value < lo else ("WARN" if value < hi else "DANGER")
            ex = 0.0 if lv == "SAFE" else value / (lo if lv == "WARN" else hi)
            return lv, f"안전 <{lo:g} / 경고 {lo:g}~{hi:g} / 위험 ≥{hi:g} °C", ex, ""
        if kind == "current_ratio":
            r = c["current_ratio"]
            sl, sh, do, du = (float(r[k]) for k in ("safe_low", "safe_high", "danger_over", "danger_under"))
            if value > do:
                lv, ex, note = "DANGER", value / do, "위험 과전류"
            elif value > sh:
                lv, ex, note = "WARN", value / sh, "주의 과전류"
            elif value < du:
                lv, ex, note = "DANGER", du / max(value, 1e-9), "위험 저전류(결상 의심)"
            elif value < sl:
                lv, ex, note = "WARN", sl / max(value, 1e-9), "주의 저전류"
            else:
                lv, ex, note = "SAFE", 0.0, "정상"
            return lv, f"안전 {sl:g}~{sh:g} / 경고 {sh:g}~{do:g} 또는 {du:g}~{sl:g} / 위험 >{do:g} 또는 <{du:g} (정격 대비)", ex, note
        if kind == "i2i1":
            b = c["i2i1"]
            lo, hi = float(b["safe_below"]), float(b["danger_from"])
            lv = "SAFE" if value < lo else ("WARN" if value < hi else "DANGER")
            ex = 0.0 if lv == "SAFE" else value / (lo if lv == "WARN" else hi)
            return lv, f"안전 <{lo:g} / 경고 {lo:g}~{hi:g} / 위험 ≥{hi:g}", ex, ""
        if kind == "vibration":
            w, p, a = self.vib["watch_mms"], self.vib["plan_mms"], self.vib["act_mms"]
            lv = "SAFE" if value < w else ("WARN" if value < a else "DANGER")
            ex = 0.0 if lv == "SAFE" else value / (w if lv == "WARN" else a)
            note = "정비 계획" if (lv == "WARN" and p < a and value >= p) else ("주시" if lv == "WARN" else ("즉시 조치" if lv == "DANGER" else "정상"))
            std = f" ({self.vib_standard})" if self.vib_standard else ""
            return lv, f"안전 <{w:g} / 경고 {w:g}~{a:g} / 위험 ≥{a:g} mm/s{std}", ex, note
        if kind == "bearing_index":
            b = c["bearing_index"]
            lo, hi = float(b["safe_below"]), float(b["danger_from"])
            lv = "SAFE" if value < lo else ("WARN" if value < hi else "DANGER")
            ex = 0.0 if lv == "SAFE" else value / (lo if lv == "WARN" else hi)
            return lv, f"안전 <{lo:g}배 / 경고 {lo:g}~{hi:g}배 / 위험 ≥{hi:g}배 (정상 대비)", ex, ""
        raise ValueError(f"알 수 없는 신호 종류: {kind}")

    def _downgrade_allowed(self, kind: str, value: float, component: str, cur: str) -> bool:
        """히스테리시스: cur 등급의 '진입 경계'보다 hys 만큼 안전 쪽으로 들어왔을 때만 내려간다."""
        c = self.cfg
        h = self.hys
        if kind == "temperature":
            b = self.temp_bounds(component)
            edge = float(b["danger_from"]) if cur == "DANGER" else float(b["safe_below"])
            return value < edge * (1 - h)
        if kind in ("i2i1", "bearing_index"):
            b = c[kind]
            edge = float(b["danger_from"]) if cur == "DANGER" else float(b["safe_below"])
            return value < edge * (1 - h)
        if kind == "vibration":
            edge = self.vib["act_mms"] if cur == "DANGER" else self.vib["watch_mms"]
            return value < edge * (1 - h)
        if kind == "current_ratio":
            r = c["current_ratio"]
            if value >= 1.0:   # 과전류 쪽
                edge = float(r["danger_over"]) if cur == "DANGER" else float(r["safe_high"])
                return value < edge * (1 - h)
            edge = float(r["danger_under"]) if cur == "DANGER" else float(r["safe_low"])   # 저전류 쪽: 위로 벗어나야
            return value > edge * (1 + h)
        return True

    # ------------------------------------------------------------------ 상태 갱신
    def judge_signal(self, t: float, kind: str, value: float, component: str = "-") -> SignalVerdict:
        raw_lv, thr, ex, note = self.raw(kind, value, component)
        key = (kind, component)
        cur = self._state.get(key)
        if cur is None:                                   # 첫 판정: 지속 조건 없이
            new = raw_lv
            self._since[key] = (raw_lv, t)
        else:
            prev_raw, since = self._since.get(key, (raw_lv, t))
            if prev_raw != raw_lv:
                self._since[key] = (raw_lv, t)
                since = t
            if RANK[raw_lv] > RANK[cur]:                  # 상향: 지속 시간 조건
                need = self.persist.get(kind, 0.0)
                new = raw_lv if (t - since) >= need - 1e-9 else cur
            elif RANK[raw_lv] < RANK[cur]:                # 하향: 히스테리시스
                new = raw_lv if self._downgrade_allowed(kind, value, component, cur) else cur
                if new != raw_lv and new != cur:
                    new = cur
            else:
                new = cur
        self._state[key] = new
        return SignalVerdict(kind=kind, component=component, value=float(value), level=new, raw_level=raw_lv,
                             threshold=thr, exceed=ex, note=note)

    def update(self, t: float, signals: dict) -> Verdict:
        """signals: {"temperature": {node: °C}, "current_ratio": {phase: r} | float, "i2i1": x, "vibration": mm/s, "bearing_index": x}"""
        out: list[SignalVerdict] = []
        for kind in KINDS:
            if kind not in signals or signals[kind] is None:
                continue
            v = signals[kind]
            if isinstance(v, dict):
                for comp, x in v.items():
                    out.append(self.judge_signal(t, kind, float(x), str(comp)))
            else:
                out.append(self.judge_signal(t, kind, float(v)))
        self._last_t = t
        return self._combine(t, out)

    def _combine(self, t: float, out: list[SignalVerdict]) -> Verdict:
        if not out:
            return Verdict(t=t, status="SAFE", cause_signal="-", cause_component="-", value=0.0, threshold="-", signals=[],
                           **self._deco("SAFE"))
        worst = max(out, key=lambda s: (RANK[s.level], s.exceed))
        return Verdict(t=t, status=worst.level, cause_signal=worst.kind, cause_component=worst.component,
                       value=worst.value, threshold=worst.threshold, signals=out, **self._deco(worst.level))

    def _deco(self, level: str) -> dict:
        return {"label_ko": self.cfg["labels_ko"][level], "icon": self.cfg["icons"][level], "color": self.cfg["colors"][level]}

    def reset(self) -> None:
        self._state.clear(); self._since.clear(); self._last_t = None

    # ------------------------------------------------------------------ 호환
    def map4(self, stage: str) -> str:
        """기존 4단계(normal/caution/warning/danger) → 3단계."""
        return self.cfg["mapping_4to3"][stage]

    def stateless(self, signals: dict) -> Verdict:
        """히스테리시스·지속 없이 현재값만으로 종합 (표·비교표용)."""
        j = Judge(self.cfg, self.motor, self.vib | {"standard": self.vib_standard})
        return j.update(0.0, signals)
