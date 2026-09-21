# -*- coding: utf-8 -*-
"""fault_injector.py — v2 인터페이스 래퍼: FaultInjector(t, s, fr, theta) 시그니처. 구현은 s5_fault_injector 와 공유(검증 완료 모듈)."""
import math
from s5_fault_injector import FaultInjector as _Base, bearing_freqs, SEV

class FaultInjector(_Base):
    def torque_v2(self, t, s, fr, theta):
        """실시간 슬립 s·회전주파수 fr 을 외부(토크 제어 루프)에서 받는다. 내부 구현은 ω 로 환산해 동일 식을 사용."""
        omega = 2 * math.pi * fr
        return self.torque(t, omega, theta)
