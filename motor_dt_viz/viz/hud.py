# -*- coding: utf-8 -*-
"""hud.py — 발표용 HUD (omni.ui). GUI 모드에서만 동작한다.

표시 항목 (CLAUDE.md §7):
  · 부품별 온도와 상태 등급
  · 상별 I_rms, I₂/I₁
  · 색상 범례
  · 정직성 라벨: "시뮬레이션 기반 추정값 (Simulation-based)" + 정격 기준 출처
"""
from __future__ import annotations

try:
    from engine.config_loader import load as _load_cfg
    PHASE_LABEL = dict(_load_cfg("electrical").get("phase_labels") or {})
except Exception:   # config 를 못 읽어도 HUD 는 떠야 한다
    PHASE_LABEL = {}

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.config_loader import load
from viz.colormap import ElectricalColormap

# ⚠️ omni.ui 기본 폰트에 한글 글리프가 없어 한글은 '??' 로 깨진다.
#    style={"font": <ttf 경로>} 로 지정해도 Isaac Sim 4.5 에서는 적용되지 않았다(실측).
#    깨진 글자를 띄우는 것보다 낫기 때문에 HUD 는 영문/숫자로 표기한다.
#    한국어 자막이 필요하면 Movie Capture 후 편집 자막으로 넣거나, 뷰포트 밖 발표 자료로 보완한다.
def _style(size: int, color: int = 0xFFFFFFFF, **extra) -> dict:
    return {"font_size": size, "color": color, **extra}


STAGE_LABEL = {"normal": "NORMAL", "caution": "CAUTION", "warning": "WARNING", "danger": "DANGER"}
STATUS_LABEL = {"over_danger": "OVER-CURRENT (HIGH)", "over_caution": "OVER-CURRENT",
                "normal": "NORMAL", "under_caution": "UNDER-CURRENT",
                "under_danger": "UNDER-CURRENT (LOW)"}


def _hex(rgb) -> int:
    """(r,g,b) 0~1 → omni.ui 0xAABBGGRR."""
    r, g, b = (max(0, min(int(c * 255), 255)) for c in rgb)
    return 0xFF000000 | (b << 16) | (g << 8) | r


class MotorHUD:
    """omni.ui 창 기반 HUD. Isaac Sim GUI 에서만 생성된다."""

    # 내용이 창보다 길면 omni.ui 가 스크롤해 제목·자막이 위로 밀려난다(실측).
    # 자막이 발표의 핵심이므로 창을 내용보다 넉넉하게 잡는다.
    def __init__(self, title: str = "VIGENT - Motor Digital Twin", width: int = 430, height: int = 790):
        import omni.ui as ui
        self.ui = ui
        self.elec = load("electrical")
        self.colors = load("colors")
        self.ecmap = ElectricalColormap(self.colors)
        self.window = ui.Window(title, width=width, height=height)
        try:
            self.window.position_x, self.window.position_y = 1010, 60   # 뷰포트를 가리지 않으면서 화면 안에 들어오게
        except Exception:
            pass
        self._labels: dict[str, object] = {}
        self._build()

    # ------------------------------------------------------------------ 구성
    def _build(self) -> None:
        ui = self.ui
        with self.window.frame:
            # margin 은 VStack 자신이 아니라 모든 자식 위젯에 상속돼 행 높이를 부풀린다(실측).
            # 값을 키우면 범례와 정직성 라벨이 창 밖으로 밀려난다.
            with ui.VStack(spacing=4, style={"margin": 3}):
                # 타임코드: 녹화 영상과 로그 CSV 의 시간축을 맞추는 기준이다.
                # 영상 첫 프레임에서 이 값을 읽으면 오프셋을 직접 확인할 수 있다.
                with ui.HStack(height=26):
                    self._labels["subtitle"] = ui.Label("", style=_style(20))
                    self._labels["timecode"] = ui.Label("", width=96,
                                                        style=_style(17, 0xFF66DDFF))
                # 자막은 창 폭(430px)보다 길어 두세 줄로 접힌다.
                self._labels["phase"] = ui.Label("", height=56, word_wrap=True,
                                                 style=_style(15, 0xFFCCCCCC))
                # 장면별 데이터 출처 (정직성 표기). scenario yaml 의 source 필드.
                self._labels["source"] = ui.Label("", height=16, word_wrap=True,
                                                  style=_style(12, 0xFF99BBAA))
                ui.Separator(height=6)

                # 전기 섹션 — 기계 전용 모드에서 통째로 숨긴다
                self._sec_current = ui.VStack(spacing=4)
                with self._sec_current:
                    ui.Label("CURRENT (MCSA)", style=_style(16, 0xFF66DDFF))
                    with ui.VStack(spacing=2):
                        for ph in ("A", "B", "C"):
                            with ui.HStack(height=20):
                                ui.Label(f"Ph {PHASE_LABEL.get(ph, ph)}", width=40, style=_style(14))   # 표시 이름은 config phase_labels (R/S/T)
                                self._labels[f"i_{ph}"] = ui.Label("-", width=140, style=_style(14))
                                self._labels[f"st_{ph}"] = ui.Label("-", width=150, style=_style(13))
                    with ui.HStack(height=26):
                        ui.Label("I2/I1", width=60, style=_style(16, 0xFFFFAA33))
                        self._labels["i2i1"] = ui.Label("-", style=_style(18, 0xFFFFAA33))
                    ui.Separator(height=6)

                # 기계 섹션 — 전기 전용 모드에서 통째로 숨긴다
                self._sec_thermal = ui.VStack(spacing=4)
                with self._sec_thermal:
                    ui.Label("COMPONENT TEMPERATURE", style=_style(16, 0xFF66DDFF))
                    self._temp_stack = ui.VStack(spacing=2)
                    ui.Separator(height=6)
                    with ui.HStack(height=20):
                        ui.Label("VIBRATION", width=90, style=_style(14))
                        self._labels["vib"] = ui.Label("-", style=_style(14))
                    ui.Separator(height=6)

                # 범례는 모드마다 하나만 띄운다. 둘 다 띄우면 정직성 라벨이 창 밖으로 밀린다.
                ui.Label("LEGEND", style=_style(15, 0xFF66DDFF))
                elec_legend = (("Over-current", self.colors["electrical"]["over_danger"]["color"]),
                               ("Normal", self.colors["electrical"]["normal"]["color"]),
                               ("Under-current", self.colors["electrical"]["under_danger"]["color"]),
                               ("Short-turn loop", self.colors["electrical"]["short_loop"]["color"]))
                st = self.colors["status"]
                therm_legend = (("Normal", st["normal"]), ("Caution", st["caution"]),
                                ("Warning", st["warning"]), ("Danger (glowing)", st["danger"]))
                self._legend_elec = ui.VStack(spacing=1)
                with self._legend_elec:
                    self._legend_rows(elec_legend)
                self._legend_therm = ui.VStack(spacing=1)
                with self._legend_therm:
                    self._legend_rows(therm_legend)
                ui.Spacer()

                # 정직성 라벨 (항상 표시, CLAUDE.md 규칙 4)
                ui.Separator(height=4)
                ui.Label("SIMULATION-BASED ESTIMATE (not measured)",
                         style=_style(14, 0xFF55FF55))
                # 쓰지 않은 모델을 적지 않도록 모드마다 문구를 바꾼다 (set_mode 에서 갱신)
                self._labels["basis"] = ui.Label("", style=_style(12, 0xFFAAAAAA),
                                                 word_wrap=True, height=30)

    def _legend_rows(self, entries) -> None:
        """범례를 2열 × 2줄로 그린다 (세로 4줄이면 아래 라벨이 창 밖으로 밀린다)."""
        ui = self.ui
        for row in (entries[:2], entries[2:]):
            with ui.HStack(height=18, spacing=8):
                for text, rgb in row:
                    with ui.HStack(width=190):
                        ui.Rectangle(width=16, height=12,
                                     style={"background_color": _hex(rgb)})
                        ui.Spacer(width=6)
                        ui.Label(text, style=_style(13))

    # ------------------------------------------------------------------ 모드
    def set_mode(self, mode: str) -> None:
        """모드에 맞는 섹션만 남긴다.

        mechanical : 온도·진동만          electrical : 전류만
        integrated : 둘 다 (범례는 전류용 — 두 범례를 같이 띄우면 창을 넘는다)
        """
        show_elec = mode in ("electrical", "integrated")
        show_therm = mode in ("mechanical", "thermal", "integrated")
        self._sec_current.visible = show_elec
        self._sec_thermal.visible = show_therm
        self._legend_elec.visible = show_elec
        self._legend_therm.visible = show_therm and not show_elec
        basis = "22 kW 6-pole hoist motor (JW-01-HTO-00)"
        if show_therm:
            basis += " / lumped thermal network"
        if show_elec:
            basis += " / analytic current model / slow motion x1/60"
        self._labels["basis"].text = basis

    # ------------------------------------------------------------------ 갱신
    def update_current(self, state) -> None:
        """CurrentState 로 전류 표시를 갱신한다."""
        for i, ph in enumerate(("A", "B", "C")):
            rms, ratio, status = state.rms_A[i], state.ratio[i], state.status[i]
            self._labels[f"i_{ph}"].text = f"{rms:6.1f} A  ({ratio * 100:5.1f} %)"
            col = self.ecmap.sample(status)["diffuse"]
            lab = self._labels[f"st_{ph}"]
            lab.text = STATUS_LABEL.get(status, status)
            lab.style = _style(14, _hex(col))
        self._labels["i2i1"].text = f"{state.i2_over_i1:.4f}"

    def update_thermal(self, temperatures: dict, stages: dict, labels: dict,
                       keys: list[str] | None = None) -> None:
        """부품 온도 목록을 갱신한다 (표시할 키만)."""
        ui = self.ui
        keys = keys or list(temperatures)
        status_colors = self.colors["status"]
        if not self._labels.get("_temp_rows"):
            self._labels["_temp_rows"] = {}
            with self._temp_stack:
                for k in keys:
                    with ui.HStack(height=19):
                        ui.Label(labels.get(k, k), width=110, style=_style(14))
                        self._labels["_temp_rows"][k] = ui.Label("-", style=_style(14))
        for k in keys:
            row = self._labels["_temp_rows"].get(k)
            if not row:
                continue
            stage = stages.get(k, "normal")
            row.text = f"{temperatures[k]:6.1f} C   {STAGE_LABEL.get(stage, stage)}"
            row.style = _style(14, _hex(status_colors.get(stage, [1, 1, 1])))

    def update_scenario(self, label: str, subtitle: str, source: str = "") -> None:
        self._labels["subtitle"].text = label
        self._labels["phase"].text = subtitle
        # source 는 영문이어야 한다 — HUD 폰트에 한글 글리프가 없다(파일 상단 주석 참고)
        self._labels["source"].text = f"Source: {source}" if source else ""

    def update_timecode(self, t_s: float | None) -> None:
        """로그 CSV 의 t_s 를 화면에 띄운다. None 이면 비운다(발표용)."""
        self._labels["timecode"].text = "" if t_s is None else f"t {t_s:6.2f}s"

    def update_vibration(self, mms: float, zone: str) -> None:
        col = {"Normal": [0.15, 0.95, 0.35], "Watch": [1.0, 0.75, 0.1],
               "Plan": [1.0, 0.45, 0.1], "Act": [1.0, 0.1, 0.05]}.get(zone, [1, 1, 1])
        lab = self._labels["vib"]
        lab.text = f"{mms:.1f} mm/s   ISO 20816-3: {zone}"
        lab.style = _style(14, _hex(col))
