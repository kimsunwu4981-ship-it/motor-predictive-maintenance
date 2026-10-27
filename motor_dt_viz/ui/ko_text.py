# -*- coding: utf-8 -*-
"""ko_text.py — omni.ui 에 한글 라벨을 그리는 보조 (패널 Q1, 2026-10-27).

실측(tools/live/ui_font_probe.py): Isaac Sim 4.5 omni.ui 는 기본 폰트에도 style font / --/app/font/file 에도 한글 글리프가 없어 '??' 로 찍힌다.
그래서 글자를 PIL 로 비트맵(RGBA)에 그려 ui.ByteImageProvider + ui.ImageWithProvider 로 띄운다. 값이 바뀔 때만 다시 그린다.
버튼·콤보박스의 글자(위젯 내부 텍스트)는 바꿀 수 없어 ASCII 로 두고, 그 옆·위에 한글 설명 라벨을 둔다.
폰트는 Windows 맑은 고딕(C:/Windows/Fonts/malgun.ttf); 없으면 PIL 기본 폰트(한글 불가).
"""
from __future__ import annotations

import os
import tempfile

FONT_CANDIDATES = [os.environ.get("VIGENT_UI_FONT", ""), r"C:\Windows\Fonts\malgun.ttf", r"C:\Windows\Fonts\malgunbd.ttf", r"C:\Windows\Fonts\gulim.ttc", r"C:\Windows\Fonts\NanumGothic.ttf"]
_FONT_CACHE: dict = {}


def find_font() -> str | None:
    for p in FONT_CANDIDATES:
        if p and os.path.exists(p):
            return p
    return None


def _font(px: int):
    from PIL import ImageFont
    if px in _FONT_CACHE:
        return _FONT_CACHE[px]
    p = find_font()
    f = None
    if p:
        try:
            f = ImageFont.truetype(p, px)
        except Exception:  # noqa: BLE001
            f = None
    if f is None:
        f = ImageFont.load_default()
    _FONT_CACHE[px] = f
    return f


def render_text(text: str, px: int = 14, color=(230, 234, 240, 255), pad: int = 2, bold: bool = False):
    """텍스트 → (PIL RGBA Image). 배경 투명."""
    from PIL import Image, ImageDraw
    f = _font(px)
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    w, h = max(int(r - l) + 2 * pad + (1 if bold else 0), 2), max(int(b - t) + 2 * pad, 2)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad - l, pad - t), text, font=f, fill=tuple(color))
    if bold:
        d.text((pad - l + 1, pad - t), text, font=f, fill=tuple(color))
    return img


class KoLabel:
    """한글 라벨 위젯 (ui 컨테이너의 with 블록 안에서 생성). 비트맵을 PNG 파일로 저장하고 ui.Image 로 띄운다(ByteImageProvider 는 실측에서 크기가 깨졌다).
    .text / .color / .set() 으로 갱신 — 같은 텍스트·색은 파일을 재사용한다."""

    def __init__(self, ui, text: str, px: int = 14, color=(230, 234, 240, 255), bold: bool = False, width: int | None = None):
        self.ui = ui
        self.px, self._color, self.bold = int(px), tuple(color), bool(bold)
        self._text = str(text)
        self._fixed_w = width
        path, w, h = ko_png_size(self._text or " ", self.px, self._color, self.bold)
        self.image = ui.Image(path, width=ui.Pixel(width or w), height=ui.Pixel(h), fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT, alignment=ui.Alignment.LEFT_CENTER)

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self.set(value)

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, rgba) -> None:
        self.set(self._text, rgba)

    def set(self, text: str, color=None) -> None:
        changed = False
        if str(text) != self._text:
            self._text = str(text); changed = True
        if color is not None and tuple(color) != self._color:
            self._color = tuple(color); changed = True
        if changed:
            self._draw()

    def _draw(self) -> None:
        path, w, h = ko_png_size(self._text or " ", self.px, self._color, self.bold)
        self.image.source_url = path
        if not self._fixed_w:
            self.image.width = self.ui.Pixel(w)
        self.image.height = self.ui.Pixel(h)


_PNG_DIR = None
_SIZE_CACHE: dict = {}


def ko_png_size(text: str, px: int = 14, color=(230, 234, 240, 255), bold: bool = False) -> tuple[str, int, int]:
    """한글 텍스트 → PNG 파일 경로와 (w, h). 같은 텍스트·크기·색은 파일을 재사용한다 (세션 임시 폴더)."""
    global _PNG_DIR
    if _PNG_DIR is None:
        _PNG_DIR = tempfile.mkdtemp(prefix="vigent_ko_")
    import hashlib
    key = hashlib.md5(f"{text}|{px}|{color}|{bold}".encode("utf-8")).hexdigest()[:16]
    p = os.path.join(_PNG_DIR, key + ".png")
    if key in _SIZE_CACHE and os.path.exists(p):
        return p.replace("\\", "/"), *_SIZE_CACHE[key]
    img = render_text(text, px, color, bold=bold)
    img.save(p)
    _SIZE_CACHE[key] = (img.width, img.height)
    return p.replace("\\", "/"), img.width, img.height


def ko_png(text: str, px: int = 14, color=(230, 234, 240, 255), bold: bool = False) -> str:
    """한글 텍스트를 PNG 파일로 (ui.Button(image_url=…) 용)."""
    return ko_png_size(text, px, color, bold)[0]


def rgba_from_hex(argb: int) -> tuple[int, int, int, int]:
    """omni.ui 색(0xAABBGGRR) → (R, G, B, A)."""
    return (argb & 0xFF, (argb >> 8) & 0xFF, (argb >> 16) & 0xFF, (argb >> 24) & 0xFF)
