# -*- coding: utf-8 -*-
"""motor_torque_model.py — 유도전동기 토크-슬립 특성 + 부하 모델 (E2). 순수 수식, Isaac 무관.

T_motor(s): 정격 운전점 부근 선형 근사 T = T_rated · s / s_rated (IEC 60034 정격점 정의, CALC)
            기동 구간: |T| ≤ T_max = T_rated × 기동토크비(2.5, 미확인(추정)) 로 클립 — 램프 기동 대신 토크 제한(직입 기동 근사).
            (Kloss 근사는 s_max 미확인이라 채택하지 않음: s_max 없이 T_max 만으로 정의되는 선형+클립이 출처 최소)
기계 감쇠 b: 베어링·풍손 근사 — 정격 출력의 1 %(≈220 W) @ 정격 각속도 → T_f ≈ 1.8 N·m → b = 0.015 N·m·s/rad, 미확인(추정)
부하: 권상 정격 환산 일정 토크 T_load = k × T_rated (k = 0.5 / 1.0)
"""
import math

class InductionMotorTorque:
    def __init__(self, cfg):
        V = lambda d: d["value"] if isinstance(d, dict) else d
        m = cfg["motor"]
        self.fs = float(V(m["supply_Hz"])); self.p = int(V(m["poles"]))
        self.n_sync = float(V(m["sync_rpm"])); self.w_sync = self.n_sync * 2 * math.pi / 60
        self.n_rated = float(V(m["rated_rpm"])); self.s_rated = (self.n_sync - self.n_rated) / self.n_sync
        self.T_rated = float(V(m["rated_torque_Nm"])); self.T_max = self.T_rated * float(V(m["starting_torque_ratio"]))
        self.b_mech = float(V(cfg["torque_control"]["mech_damping_Nms_per_rad"]))
    def slip(self, omega):
        return (self.w_sync - omega) / self.w_sync
    def torque(self, omega):
        s = self.slip(omega); T = self.T_rated * s / self.s_rated
        return max(-self.T_max, min(self.T_max, T)), s
    def friction(self, omega):
        return -self.b_mech * omega
    def expected_operating_point(self, T_load):
        """정상 상태: T_rated·s/s_rated − b·ω_sync(1−s) = T_load → s 해석해"""
        a = self.T_rated / self.s_rated; b = self.b_mech * self.w_sync
        s = (T_load + b) / (a + b)
        return {"slip": s, "rpm": self.n_sync * (1 - s), "T_motor": a * s}

class ConstantLoad:
    def __init__(self, T_rated, fraction):
        self.T = T_rated * fraction
    def torque(self, omega):
        # 저속(|ω|<1 rad/s)에서 선형 감소 → 정지 시 수치 진동 방지
        return -self.T * (1.0 if omega > 1.0 else max(omega, 0.0))
