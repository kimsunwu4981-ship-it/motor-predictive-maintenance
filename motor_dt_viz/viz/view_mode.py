# -*- coding: utf-8 -*-
"""view_mode.py — M1 모델 뷰(USD variantSet "view") 전환의 **유일한 진입점** (fix/panel-view-switch, 2026-10-27).

  VIEW = ViewMode(m1, log=print)
  VIEW.set("windings_only", source="manual")      # 패널 버튼 · 시나리오 장면 · --cam_plan · 시작값 — 전부 여기로
  VIEW.xray(on)                                  # 단락 루프 강조(x-ray) 는 임시 cutaway — 켜짐/꺼짐 '변화' 때만 1회 (매 프레임 재적용 금지)
  VIEW.mode / VIEW.source / VIEW.readback()      # 실제 USD 선택값으로 확인 — 버튼 색·state.view_mode 는 이 값

왜: 예전 메인 루프가 materials 구간에서 매 프레임 `m1.set_view(args.view)` 를 불러, 패널이 바꾼 variant 가 다음 프레임에 되돌아갔다(§1 진단 로그).
"""
from __future__ import annotations

MODES = ("full", "half_translucent", "half_translucent_front", "cutaway", "windings_only")
LABEL_KO = {"full": "전체", "half_translucent": "반절 반투명", "half_translucent_front": "반절 반투명(앞)", "cutaway": "절단", "windings_only": "권선만"}
PANEL_MAP = {"반투명": "half_translucent", "절단": "cutaway", "권선만": "windings_only"}   # 패널 버튼 라벨 ↔ 모드


class ViewMode:
    def __init__(self, m1, log=print):
        self.m1, self.log = m1, log
        self.mode: str | None = None          # 실제 적용된 모드 (readback)
        self.base: str | None = None          # 사용자·시나리오가 고른 뷰 (xray 임시 전환의 복귀 지점)
        self.source: str = "startup"          # startup | manual | scenario | cam_plan | xray
        self._xray = False
        self.last_error: str | None = None

    def readback(self) -> str | None:
        try:
            vs = self.m1.prim.GetVariantSet("view")
            return vs.GetVariantSelection() if vs else None
        except Exception as e:  # noqa: BLE001
            self.last_error = str(e)
            return None

    def available(self) -> list[str]:
        try:
            vs = self.m1.prim.GetVariantSet("view")
            return list(vs.GetVariantNames()) if vs else []
        except Exception:  # noqa: BLE001
            return []

    def set(self, mode: str, source: str = "manual") -> str | None:
        """variant 선택 → USD 를 다시 읽어 실제값을 돌려준다(실패·미지원이면 None + 경고 로그). 같은 값이면 로그 없이 그대로."""
        if mode not in MODES:
            self.last_error = f"unknown view mode {mode!r}"
            self.log(f"[view] WARNING {self.last_error}")
            return None
        if mode == self.mode and mode == self.base and not self._xray:
            self.source = source
            return self.mode
        self.m1.set_view(mode)
        actual = self.readback()
        if actual != mode:
            self.last_error = f"variant not applied: wanted {mode}, usd={actual}, available={self.available()}"
            self.log(f"[view] WARNING {self.last_error}")
        else:
            self.last_error = None
            self.log(f"[view] variant → {mode} ({source})")
        self.mode = actual
        self.base = mode if actual == mode else self.base
        self.source = source
        self._xray = False
        return actual

    def xray(self, on: bool) -> None:
        """단락 루프 강조: 켜지는 순간 cutaway(반투명 계열이면 그대로), 꺼지는 순간 base 로 복귀. 변화 없으면 아무 것도 안 한다."""
        if on == self._xray:
            return
        self._xray = on
        base = self.base or self.mode or "full"
        if on:
            if not base.startswith("half_translucent"):
                self.m1.set_view("cutaway")
                self.mode = self.readback()
                self.source = "xray"
                self.log(f"[view] xray on → cutaway (base {base})")
        else:
            self.m1.set_view(base)
            self.mode = self.readback()
            self.source = "xray_off"
            self.log(f"[view] xray off → {base}")

    def state(self) -> dict:
        return {"view_mode": self.mode, "view_source": self.source, "view_label": LABEL_KO.get(self.mode or "", self.mode)}
