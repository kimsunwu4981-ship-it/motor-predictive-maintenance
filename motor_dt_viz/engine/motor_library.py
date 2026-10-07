# -*- coding: utf-8 -*-
"""motor_library.py — 보편 크레인 권상 모터 5종 라이브러리 (config/motors/<id>.yaml). Isaac Sim 비의존.

역할 (TASK_다중모터 §4):
  1) YAML 로드 + 스키마 검증 (필수 키, 단위, 범위, 선/상전류 정합)
  2) 파생값: 회전 주파수 fr, 동기속도 검산, 슬립, 상전류, 베어링 결함 주파수(BPFO/BPFI Hz)
  3) 기존 엔진에 꽂기: motor.yaml 모양의 dict(→ MotorSpec), M5 기준 스케일된 thermal cfg, electrical cfg
  4) 진동 규격 선택: 15 kW 미만 ISO 10816-1 Class I / 15 kW 이상 ISO 20816-3 Group 2 (규칙 4)

열회로 스케일 규칙 (§4.2, docs/thermal_scaling.md):
  손실 P_loss ∝ P_rated·(1−η)/η            → 노드 정격 손실·브레이크 끌림 추가 손실에 비율 적용
  열저항 R ∝ 1/표면적 = 1/geometry_scale²   → R_amb, 커플링 R_ij
  열용량 C ∝ 질량 = geometry_scale³         → 노드 질량
  M5(geometry_scale 1.0, 손실비 1.0)는 config/thermal.yaml 과 완전히 같아야 한다 (회귀 테스트).

모터 고유값은 YAML 에만 있다. 이 모듈에 kW·전류·임계값 숫자를 쓰지 않는다.
"""
from __future__ import annotations

import copy
import math
import os
from dataclasses import dataclass, field
from functools import lru_cache

import yaml

from .config_loader import CONFIG_DIR, MotorSpec, load, val

MOTORS_DIR = os.path.join(CONFIG_DIR, "motors")
REFERENCE_ID = "M5"          # 열회로 튜닝 기준 모터 (현 프로젝트 22 kW, thermal.yaml 의 값)
VIB_STANDARD_SPLIT_KW = 15.0  # 규칙 4: 15 kW 미만 10816-1, 이상 20816-3

REQUIRED = ("id", "name", "source", "rated_power_kw", "poles", "sync_rpm", "rated_rpm", "voltage_v", "frequency_hz",
            "connection", "efficiency", "power_factor", "rated_line_current_a", "rated_phase_current_a", "frame",
            "insulation_class", "duty", "bearing_de", "bearing_nde", "bearing_fault_multipliers", "geometry_scale",
            "thermal", "vibration")


class MotorLibraryError(ValueError):
    pass


@dataclass
class Motor:
    """YAML 한 장 = 모터 하나. 파생값은 property."""
    raw: dict
    id: str
    name: str
    source: str
    rated_power_kw: float
    poles: int
    sync_rpm: float
    rated_rpm: float
    voltage_v: float
    frequency_hz: float
    connection: str
    efficiency: float
    power_factor: float
    rated_line_current_a: float
    rated_phase_current_a: float
    frame: str
    insulation_class: str
    duty: str
    bearing_de: str
    bearing_nde: str
    bpfo_mult: float
    bpfi_mult: float
    bpfo_mult_nde: float | None
    bpfi_mult_nde: float | None
    bearing_source: str
    geometry_scale: float
    vibration: dict = field(default_factory=dict)   # {standard, watch_mms, plan_mms, act_mms}
    tags: dict = field(default_factory=dict)        # 용도·톤수 등 표시용

    # ---- 파생값 ----
    @property
    def rotor_freq_hz(self) -> float:
        return self.rated_rpm / 60.0

    @property
    def slip(self) -> float:
        return (self.sync_rpm - self.rated_rpm) / self.sync_rpm

    @property
    def torque_nm(self) -> float:
        return 9550.0 * self.rated_power_kw / self.rated_rpm

    @property
    def loss_w(self) -> float:
        """정격 전손실 ≈ P·(1−η)/η [W]."""
        return self.rated_power_kw * 1000.0 * (1.0 - self.efficiency) / self.efficiency

    def bpfo_hz(self, rpm: float | None = None) -> float:
        return self.bpfo_mult * ((rpm or self.rated_rpm) / 60.0)

    def bpfi_hz(self, rpm: float | None = None) -> float:
        return self.bpfi_mult * ((rpm or self.rated_rpm) / 60.0)

    @property
    def vib_thresholds(self) -> dict:
        """{standard, watch_mms, plan_mms, act_mms} — 모터 YAML 의 vibration 블록 (규칙 4 로 채워짐)."""
        return dict(self.vibration)


# ----------------------------------------------------------------------------- 로드·검증
def list_ids() -> list[str]:
    if not os.path.isdir(MOTORS_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(MOTORS_DIR) if f.endswith(".yaml"))


def _num(d: dict, key: str, lo: float, hi: float, mid: str) -> float:
    v = val(d.get(key))
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        raise MotorLibraryError(f"{mid}: {key} 는 숫자여야 한다 (현재 {v!r})")
    if not (lo <= float(v) <= hi):
        raise MotorLibraryError(f"{mid}: {key}={v} 가 허용 범위 [{lo}, {hi}] 밖이다")
    return float(v)


def validate(d: dict) -> None:
    mid = d.get("id", "?")
    missing = [k for k in REQUIRED if k not in d]
    if missing:
        raise MotorLibraryError(f"{mid}: 필수 키 누락 {missing}")
    if d["source"] not in ("nameplate", "representative"):
        raise MotorLibraryError(f"{mid}: source 는 nameplate | representative")
    p = _num(d, "rated_power_kw", 0.1, 500.0, mid)
    poles = int(_num(d, "poles", 2, 12, mid))
    if poles % 2:
        raise MotorLibraryError(f"{mid}: poles 는 짝수")
    f = _num(d, "frequency_hz", 50.0, 60.0, mid)
    v = _num(d, "voltage_v", 200.0, 700.0, mid)
    sync = _num(d, "sync_rpm", 100.0, 4000.0, mid)
    if abs(sync - 120.0 * f / poles) > 0.5:
        raise MotorLibraryError(f"{mid}: sync_rpm {sync} ≠ 120·f/p = {120 * f / poles:.1f}")
    rated = _num(d, "rated_rpm", 100.0, 4000.0, mid)
    if not (0.0 < (sync - rated) / sync < 0.10):
        raise MotorLibraryError(f"{mid}: 슬립 (sync−rated)/sync 가 0~10 % 범위를 벗어난다 ({sync}→{rated})")
    eta = _num(d, "efficiency", 0.5, 1.0, mid)
    pf = _num(d, "power_factor", 0.5, 1.0, mid)
    il = _num(d, "rated_line_current_a", 0.1, 2000.0, mid)
    ip = _num(d, "rated_phase_current_a", 0.1, 2000.0, mid)
    if d["connection"] not in ("delta", "star"):
        raise MotorLibraryError(f"{mid}: connection 은 delta | star")
    expect_ip = il / math.sqrt(3) if d["connection"] == "delta" else il
    if abs(ip - expect_ip) / expect_ip > 0.03:
        raise MotorLibraryError(f"{mid}: 상전류 {ip} A 가 선전류/√3 = {expect_ip:.2f} A 와 3 % 넘게 다르다")
    calc_il = p * 1000.0 / (math.sqrt(3) * v * eta * pf)
    if abs(calc_il - il) / il > 0.05:
        raise MotorLibraryError(f"{mid}: 선전류 {il} A 가 P/(√3·V·η·cosφ) = {calc_il:.1f} A 와 5 % 넘게 다르다")
    _num(d, "geometry_scale", 0.2, 2.0, mid)
    bm = d["bearing_fault_multipliers"]
    for k in ("bpfo", "bpfi", "source"):
        if k not in bm:
            raise MotorLibraryError(f"{mid}: bearing_fault_multipliers.{k} 누락")
    if bm["source"] not in ("catalog", "nameplate", "estimated", "MFR"):
        raise MotorLibraryError(f"{mid}: bearing_fault_multipliers.source 값 오류")
    if not (1.0 < float(bm["bpfo"]) < float(bm["bpfi"]) < 20.0):
        raise MotorLibraryError(f"{mid}: BPFO < BPFI, 1~20 배 범위여야 한다")
    th = d["thermal"]
    if th.get("scale_rule") != "power_ratio":
        raise MotorLibraryError(f"{mid}: thermal.scale_rule 은 power_ratio 만 지원")
    vib = d["vibration"]
    for k in ("standard", "watch_mms", "plan_mms", "act_mms"):
        if k not in vib:
            raise MotorLibraryError(f"{mid}: vibration.{k} 누락")
    if not (0 < float(vib["watch_mms"]) <= float(vib["plan_mms"]) <= float(vib["act_mms"])):
        raise MotorLibraryError(f"{mid}: 진동 경계는 watch ≤ plan ≤ act")
    want = "ISO 10816-1" if p < VIB_STANDARD_SPLIT_KW else "ISO 20816-3"
    if not str(vib["standard"]).startswith(want):
        raise MotorLibraryError(f"{mid}: {p} kW 는 {want} 를 써야 한다 (규칙 4), 현재 {vib['standard']}")


@lru_cache(maxsize=None)
def load_motor(mid: str) -> Motor:
    path = os.path.join(MOTORS_DIR, f"{mid}.yaml")
    if not os.path.exists(path):
        raise MotorLibraryError(f"config/motors/{mid}.yaml 이 없다 (있는 것: {list_ids()})")
    with open(path, encoding="utf-8") as f:
        d = yaml.safe_load(f)
    validate(d)
    bm = d["bearing_fault_multipliers"]
    nde = d.get("bearing_fault_multipliers_nde") or {}
    return Motor(
        raw=d, id=d["id"], name=d["name"], source=d["source"],
        rated_power_kw=float(d["rated_power_kw"]), poles=int(d["poles"]), sync_rpm=float(d["sync_rpm"]),
        rated_rpm=float(d["rated_rpm"]), voltage_v=float(d["voltage_v"]), frequency_hz=float(d["frequency_hz"]),
        connection=d["connection"], efficiency=float(d["efficiency"]), power_factor=float(d["power_factor"]),
        rated_line_current_a=float(d["rated_line_current_a"]), rated_phase_current_a=float(d["rated_phase_current_a"]),
        frame=str(d["frame"]), insulation_class=str(d["insulation_class"]), duty=str(d["duty"]),
        bearing_de=str(d["bearing_de"]), bearing_nde=str(d["bearing_nde"]),
        bpfo_mult=float(bm["bpfo"]), bpfi_mult=float(bm["bpfi"]),
        bpfo_mult_nde=float(nde["bpfo"]) if nde else None, bpfi_mult_nde=float(nde["bpfi"]) if nde else None,
        bearing_source=str(bm["source"]), geometry_scale=float(d["geometry_scale"]),
        vibration={k: (float(v) if k in ("watch_mms", "plan_mms", "act_mms") else str(v)) for k, v in d["vibration"].items()},
        tags=dict(d.get("tags") or {}),
    )


def load_all() -> dict[str, Motor]:
    return {mid: load_motor(mid) for mid in list_ids()}


# ----------------------------------------------------------------------------- 베어링 결함 주파수 (대표 기하)
def bearing_multipliers(n_balls: int, ball_d_mm: float, pitch_d_mm: float, contact_deg: float = 0.0) -> tuple[float, float]:
    """BPFO = n/2·(1−(d/D)cosα), BPFI = n/2·(1+(d/D)cosα)  [× fr]. 카탈로그 값이 없을 때 쓴다 (source: estimated)."""
    k = (ball_d_mm / pitch_d_mm) * math.cos(math.radians(contact_deg))
    return n_balls / 2.0 * (1.0 - k), n_balls / 2.0 * (1.0 + k)


# ----------------------------------------------------------------------------- 기존 엔진에 꽂기
def motor_spec_cfg(m: Motor) -> dict:
    """config/motor.yaml 과 같은 모양의 dict — MotorSpec(cfg) 가 그대로 읽는다."""
    base = load("motor")
    mech = base.get("mechanics", {})
    s = m.geometry_scale
    ref_mass = float(val(base["rating"]["mass_kg"]))
    ref_inertia = float(val(mech["rotor_inertia_kgm2"]))
    mass = m.raw.get("mass_kg")
    inertia = m.raw.get("rotor_inertia_kgm2")
    return {
        "meta": {"target": m.name, "drawing": m.raw.get("drawing", ""), "basis_note": f"motor library {m.id} ({m.source})"},
        "rating": {
            "power_kW": m.rated_power_kw, "poles": m.poles, "voltage_LL_V": m.voltage_v, "frequency_Hz": m.frequency_hz,
            "connection": m.connection, "sync_rpm": m.sync_rpm, "rated_rpm": m.rated_rpm, "slip": round(m.slip, 4),
            "torque_Nm": round(m.torque_nm, 1),
            "mass_kg": float(mass) if mass is not None else round(ref_mass * s ** 3, 1),   # 없으면 scale³ 추정
        },
        "current": {"efficiency": m.efficiency, "power_factor": m.power_factor,
                    "rated_line_A": m.rated_line_current_a, "rated_phase_A": m.rated_phase_current_a, "source": m.source},
        "bearing": {"designation": m.bearing_de, "bpfo_mult": m.bpfo_mult, "bpfi_mult": m.bpfi_mult,
                    "reference_rpm": m.rated_rpm, "nde": m.bearing_nde, "source": m.bearing_source},
        "vibration": dict(m.vibration),
        "vibration_iso20816_3": {"watch_mms": m.vibration["watch_mms"], "plan_mms": m.vibration["plan_mms"],
                                 "act_mms": m.vibration["act_mms"]},   # 기존 코드 호환 키 (값은 모터 규격)
        "mechanics": {"rotor_inertia_kgm2": float(inertia) if inertia is not None else round(ref_inertia * s ** 5, 4)},
    }


def motor_spec(m: Motor) -> MotorSpec:
    return MotorSpec(motor_spec_cfg(m))


def thermal_cfg(m: Motor) -> dict:
    """M5 기준 thermal.yaml 을 §4.2 규칙으로 스케일한 cfg. M5 는 원본과 같다."""
    base = copy.deepcopy(load("thermal"))
    ref = load_motor(REFERENCE_ID)
    s = m.geometry_scale / ref.geometry_scale
    p_ratio = m.loss_w / ref.loss_w
    for node in base["nodes"].values():
        node["mass_kg"] = round(float(node["mass_kg"]) * s ** 3, 4)
        node["R_amb"] = round(float(node["R_amb"]) / s ** 2, 6)
        node["loss_W_rated"] = round(float(node["loss_W_rated"]) * p_ratio, 3)
    base["couplings"] = [[a, b, round(float(r) / s ** 2, 6)] for a, b, r in base["couplings"]]
    for fc in base["faults"].values():
        if "extra_loss_W" in fc:
            fc["extra_loss_W"] = round(float(fc["extra_loss_W"]) * p_ratio, 2)
    base["scaled_from"] = {"reference": ref.id, "motor": m.id, "geometry_scale": s, "loss_ratio": round(p_ratio, 4),
                           "rule": "P∝P(1−η)/η, R∝1/scale², C∝scale³ (docs/thermal_scaling.md)"}
    return base


def electrical_cfg(m: Motor) -> dict:
    base = copy.deepcopy(load("electrical"))
    base["source"]["honesty_sub"] = (f"정격 기준: {m.name} — {'명판' if m.source == 'nameplate' else '대표 사양(명판 아님)'} · "
                                     f"전류는 해석식 생성")
    base["motor_id"] = m.id
    return base


def is_reference(m: Motor) -> bool:
    return m.id == REFERENCE_ID
