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
  · 베어링 지표(2026-10-08 정의): 주 bearing_kurtosis(모터 공통) + 보조 bearing_hf_ratio(고주파 RMS ÷ 모터별 정상 기준선).
    베어링 종합 등급 = 둘 중 나쁜 쪽 (bearing_level). 포락선 BPFO/BPFI 는 판정에 쓰지 않는다 (결함 부위 추정 표시만, bearing_site_hint).
    온도는 persistence 0 (느린 신호). 등급 하향에는 지속 조건을 두지 않는다 (히스테리시스가 맡는다).
  · 첫 호출(상태 없음)은 지속 조건 없이 현재값으로 판정한다 (로그 중간부터 판정을 시작해도 처음부터 맞게).
  · 출처·상태·정책(P1, 2026-10-21): config 의 source/status/mode 를 읽는다. provisional 지표는 judgment.provisional_policy 에 따라
    simulation 스트림이면 종합에 포함(+ provisional 라벨), live 스트림이면 worst-of 에서 빠져 Verdict.advisory 로만 나온다.
    I₂/I₁ 이 mode: baseline_multiple 이면 경계 = baseline.value × warn/danger_multiple. 전압 보정은 enabled 이고 입력에 v2_v1 이 있을 때만.
    규칙(worst-of·히스테리시스·지속)은 바뀌지 않았다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config_loader import load

LEVELS = ("SAFE", "WARN", "DANGER")
RANK = {lv: i for i, lv in enumerate(LEVELS)}
KINDS = ("temperature", "current_ratio", "i2i1", "vibration", "bearing_kurtosis", "bearing_hf_ratio")
BEARING_KINDS = ("bearing_kurtosis", "bearing_hf_ratio")      # 베어링 종합 = 둘 중 나쁜 쪽
BEARING_CFG_KEY = {"bearing_kurtosis": "kurtosis", "bearing_hf_ratio": "hf_ratio"}


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
    status: str = "confirmed"   # 지표 기준의 상태 (config source/status): confirmed | provisional
    source: str = ""            # 기준 출처
    advisory: bool = False      # True 면 종합(worst-of)에 넣지 않은 참고 지표 (live + provisional)
    compensated: bool = False   # I₂/I₁ 전압 불평형 보정 적용 여부


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
    advisory: list[SignalVerdict] = field(default_factory=list)   # 종합에서 제외된 참고 지표 (live + provisional)
    stream: str = "simulation"
    provisional_in_status: bool = False                            # 종합 상태가 provisional 지표(임시 기준)에 의해 결정됐는가

    def as_dict(self) -> dict:
        return {"t": self.t, "status": self.status, "label": self.label_ko, "icon": self.icon, "color": self.color,
                "cause_signal": self.cause_signal, "cause_component": self.cause_component,
                "value": self.value, "threshold": self.threshold, "stream": self.stream, "provisional_in_status": self.provisional_in_status,
                "signals": [vars(s) for s in self.signals], "advisory": [vars(s) for s in self.advisory]}


def bearing_level(signals) -> str:
    """베어링 종합 등급: bearing_kurtosis·bearing_hf_ratio 의 등급 중 나쁜 쪽. signals 는 SignalVerdict 목록 또는 {kind: level}."""
    best = "SAFE"
    items = signals.items() if isinstance(signals, dict) else ((s.kind, s.level) for s in signals)
    for kind, lv in items:
        if kind in BEARING_KINDS and RANK[lv] > RANK[best]:
            best = lv
    return best


KIND_META_KEY = {"current_ratio": ("current", "rated_ratio"), "i2i1": ("current", "negative_sequence"),
                 "temperature": ("temperature",), "vibration": ("vibration",), "bearing_kurtosis": ("bearing",), "bearing_hf_ratio": ("bearing",)}


class Judge:
    def __init__(self, cfg: dict | None = None, motor=None, vib_thresholds: dict | None = None, stream: str | None = None):
        """motor: motor_library.Motor (진동 규격·정격 전류). vib_thresholds 로 직접 줄 수도 있다.
        stream: 'simulation'(DT 합성 신호) | 'live'(실측 스트림). None 이면 config judgment.stream_default (없으면 simulation)."""
        self.cfg = cfg or load("thresholds")
        self.motor = motor
        jd = self.cfg.get("judgment") or {}
        self.stream = stream or str(jd.get("stream_default", "simulation"))
        self.policy = dict(jd.get("provisional_policy") or {"simulation": "include_with_label", "live": "advisory_only"})
        vt = vib_thresholds or (motor.vib_thresholds if motor is not None else None) or self.cfg["vibration"]["fallback"]
        self.vib = {k: float(vt[k]) for k in ("watch_mms", "plan_mms", "act_mms")}
        self.vib_standard = str(vt.get("standard", ""))
        self.hys = float(self.cfg["hysteresis"]["fraction"])
        self.persist = {k: float(v) for k, v in self.cfg["persistence_s"].items()}
        self._state: dict[tuple[str, str], str] = {}        # (kind, component) → 현재 등급
        self._since: dict[tuple[str, str], tuple[str, float]] = {}   # (kind, component) → (raw 등급, 그 등급이 시작된 t)
        self._last_t: float | None = None

    # ------------------------------------------------------------------ 출처·상태·모드 (P1)
    def set_stream(self, stream: str) -> None:
        self.stream = stream

    def kind_meta(self, kind: str) -> dict:
        """config 의 source/status/mode (없으면 confirmed/absolute)."""
        d = self.cfg
        for k in KIND_META_KEY.get(kind, ()):
            d = d.get(k) if isinstance(d, dict) else None
            if d is None:
                return {"source": "", "status": "confirmed", "mode": "absolute"}
        return {"source": str(d.get("source", "")), "status": str(d.get("status", "confirmed")), "mode": str(d.get("mode", "absolute"))}

    def is_provisional(self, kind: str) -> bool:
        return self.kind_meta(kind)["status"] == "provisional"

    def i2i1_bounds(self) -> tuple[float, float, str]:
        """(경고 경계, 위험 경계, 모드). current.negative_sequence 가 있으면 그쪽(절대값 또는 baseline × 배수), 없으면 기존 i2i1 블록."""
        ns = (self.cfg.get("current") or {}).get("negative_sequence")
        if not ns:
            b = self.cfg["i2i1"]
            return float(b["safe_below"]), float(b["danger_from"]), "absolute"
        if str(ns.get("mode", "absolute")) == "baseline_multiple" and isinstance(ns.get("baseline"), dict) and ns["baseline"].get("value") is not None:
            base = float(ns["baseline"]["value"])
            return base * float(ns.get("warn_multiple", 2.0)), base * float(ns.get("danger_multiple", 4.0)), "baseline_multiple"
        return float(ns["warn"]), float(ns["danger"]), "absolute"

    def compensate_i2i1(self, value: float, v2_v1: float | None) -> tuple[float, bool]:
        """전압 불평형 보정: enabled 이고 v2_v1 이 주어졌을 때만 I₂/I₁ − k·V₂/V₁ (0 이하로는 내리지 않음)."""
        ns = (self.cfg.get("current") or {}).get("negative_sequence") or {}
        vc = ns.get("voltage_unbalance_compensation") or {}
        if vc.get("enabled") and v2_v1 is not None:
            return max(0.0, float(value) - float(vc.get("k", 1.0)) * float(v2_v1)), True
        return float(value), False

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
            lo, hi, mode = self.i2i1_bounds()
            lv = "SAFE" if value < lo else ("WARN" if value < hi else "DANGER")
            ex = 0.0 if lv == "SAFE" else value / (lo if lv == "WARN" else hi)
            tag = " (기준선 배수)" if mode == "baseline_multiple" else ""
            return lv, f"안전 <{lo:g} / 경고 {lo:g}~{hi:g} / 위험 ≥{hi:g}{tag}", ex, ""
        if kind == "vibration":
            w, p, a = self.vib["watch_mms"], self.vib["plan_mms"], self.vib["act_mms"]
            lv = "SAFE" if value < w else ("WARN" if value < a else "DANGER")
            ex = 0.0 if lv == "SAFE" else value / (w if lv == "WARN" else a)
            note = "정비 계획" if (lv == "WARN" and p < a and value >= p) else ("주시" if lv == "WARN" else ("즉시 조치" if lv == "DANGER" else "정상"))
            std = f" ({self.vib_standard})" if self.vib_standard else ""
            return lv, f"안전 <{w:g} / 경고 {w:g}~{a:g} / 위험 ≥{a:g} mm/s{std}", ex, note
        if kind in BEARING_KINDS:
            b = c["bearing"][BEARING_CFG_KEY[kind]]
            lo, hi = float(b["safe_below"]), float(b["danger_from"])
            lv = "SAFE" if value < lo else ("WARN" if value < hi else "DANGER")
            ex = 0.0 if lv == "SAFE" else value / (lo if lv == "WARN" else hi)
            if kind == "bearing_kurtosis":
                return lv, f"안전 <{lo:g} / 경고 {lo:g}~{hi:g} / 위험 ≥{hi:g} (kurtosis, 모터 공통)", ex, ""
            return lv, f"안전 <{lo:g}배 / 경고 {lo:g}~{hi:g}배 / 위험 ≥{hi:g}배 (고주파 RMS, 모터별 정상 기준선 대비)", ex, ""
        raise ValueError(f"알 수 없는 신호 종류: {kind}")

    def _downgrade_allowed(self, kind: str, value: float, component: str, cur: str) -> bool:
        """히스테리시스: cur 등급의 '진입 경계'보다 hys 만큼 안전 쪽으로 들어왔을 때만 내려간다."""
        c = self.cfg
        h = self.hys
        if kind == "temperature":
            b = self.temp_bounds(component)
            edge = float(b["danger_from"]) if cur == "DANGER" else float(b["safe_below"])
            return value < edge * (1 - h)
        if kind == "i2i1":
            lo, hi, _ = self.i2i1_bounds()
            edge = hi if cur == "DANGER" else lo
            return value < edge * (1 - h)
        if kind in BEARING_KINDS:
            b = c["bearing"][BEARING_CFG_KEY[kind]]
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
    def judge_signal(self, t: float, kind: str, value: float, component: str = "-", v2_v1: float | None = None) -> SignalVerdict:
        compensated = False
        if kind == "i2i1":
            value, compensated = self.compensate_i2i1(value, v2_v1)
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
        meta = self.kind_meta(kind)
        return SignalVerdict(kind=kind, component=component, value=float(value), level=new, raw_level=raw_lv,
                             threshold=thr, exceed=ex, note=note, status=meta["status"], source=meta["source"], compensated=compensated)

    def update(self, t: float, signals: dict) -> Verdict:
        """signals: {"temperature": {node: °C}, "current_ratio": {phase: r} | float, "i2i1": x, "vibration": mm/s,
                 "bearing_kurtosis": k, "bearing_hf_ratio": r}  (베어링 둘은 각각 판정, 종합은 bearing_level)"""
        out: list[SignalVerdict] = []
        v2v1 = signals.get("v2_v1")                     # 전압 역상비 (있을 때만 I₂/I₁ 보정에 쓴다)
        for kind in KINDS:
            if kind not in signals or signals[kind] is None:
                continue
            v = signals[kind]
            if kind == "i2i1" and isinstance(v, dict):   # {"value": x, "v2_v1": y} 꼴도 허용
                out.append(self.judge_signal(t, kind, float(v["value"]), v2_v1=v.get("v2_v1", v2v1)))
            elif isinstance(v, dict):
                for comp, x in v.items():
                    out.append(self.judge_signal(t, kind, float(x), str(comp)))
            else:
                out.append(self.judge_signal(t, kind, float(v), v2_v1=v2v1 if kind == "i2i1" else None))
        self._last_t = t
        return self._combine(t, out)

    def _combine(self, t: float, out: list[SignalVerdict]) -> Verdict:
        """종합 = worst-of (규칙 불변). P1: live 스트림 + advisory_only 정책이면 provisional 지표는 worst-of 에서 빼서 advisory 로."""
        policy = self.policy.get(self.stream, "include_with_label")
        advisory: list[SignalVerdict] = []
        if policy == "advisory_only":
            for s in out:
                if s.status == "provisional":
                    s.advisory = True
            advisory = [s for s in out if s.advisory]
        judged = [s for s in out if not s.advisory]
        base = {"advisory": advisory, "stream": self.stream}
        if not judged:
            return Verdict(t=t, status="SAFE", cause_signal="-", cause_component="-", value=0.0, threshold="-", signals=out,
                           **self._deco("SAFE"), **base)
        worst = max(judged, key=lambda s: (RANK[s.level], s.exceed))
        if worst.level == "SAFE":                      # 모두 안전: 원인 없음 (가장 임계에 가까운 신호는 signals 에서 고른다)
            return Verdict(t=t, status="SAFE", cause_signal="-", cause_component="-", value=0.0, threshold="-",
                           signals=out, **self._deco("SAFE"), **base)
        return Verdict(t=t, status=worst.level, cause_signal=worst.kind, cause_component=worst.component,
                       value=worst.value, threshold=worst.threshold, signals=out, provisional_in_status=(worst.status == "provisional"),
                       **self._deco(worst.level), **base)

    def _deco(self, level: str) -> dict:
        return {"label_ko": self.cfg["labels_ko"][level], "icon": self.cfg["icons"][level], "color": self.cfg["colors"][level]}

    # ------------------------------------------------------------------ 베어링 종합·보조 표시
    @staticmethod
    def bearing_level(signals: list[SignalVerdict]) -> str:
        """베어링 종합 등급 = kurtosis·고주파 배율 중 나쁜 쪽 (config bearing.combine: worst). 둘 다 없으면 SAFE."""
        return bearing_level(signals)

    def bearing_site_hint(self, env_bpfo_ratio: float | None, env_bpfi_ratio: float | None, bearing_known: bool) -> str:
        """결함 부위 추정 보조 표시 (판정에 쓰지 않는다). 베어링 번호를 아는 모터에서 포락선 BPFO/BPFI 피크비 중 큰 쪽이
        bearing.envelope_hint_min_ratio 이상이면 '외륜 쪽'/'내륜 쪽', 아니면 '-'."""
        b = self.cfg.get("bearing", {})
        if not b.get("envelope_hint", False) or not bearing_known or env_bpfo_ratio is None or env_bpfi_ratio is None:
            return "-"
        m = float(b.get("envelope_hint_min_ratio", 0.0))
        o, i = float(env_bpfo_ratio), float(env_bpfi_ratio)
        if o != o or i != i or max(o, i) < m:          # NaN 또는 문턱 미만
            return "-"
        return "외륜 쪽" if o >= i else "내륜 쪽"

    def reset(self) -> None:
        self._state.clear(); self._since.clear(); self._last_t = None

    # ------------------------------------------------------------------ 호환
    def map4(self, stage: str) -> str:
        """기존 4단계(normal/caution/warning/danger) → 3단계."""
        return self.cfg["mapping_4to3"][stage]

    def stateless(self, signals: dict) -> Verdict:
        """히스테리시스·지속 없이 현재값만으로 종합 (표·비교표용)."""
        j = Judge(self.cfg, self.motor, self.vib | {"standard": self.vib_standard}, stream=self.stream)
        return j.update(0.0, signals)
