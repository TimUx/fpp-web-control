"""Show a numeric code or a scrolling text on an FPP pixel overlay model
(e.g. a pixel matrix).

Used for the daily access code: the house itself displays the code, so only
people standing in front of it can read it. The scrolling text announces the
title of a wished song.

Everything is rendered here (5x7 bitmap font) instead of using FPP's text
effect, because the overlay model stored in FPP often does not describe the
real wiring of a matrix (xLights uploads e.g. "3 strings x 300 nodes" as a
300x3 model although the matrix is 36x25). The physical wiring can therefore
be configured separately; whatever is not configured is taken from FPP.

Can be run directly to test the wiring settings on the real matrix:

    python code_matrix.py --fpp http://fpp.local --model Matrix --text 123 \
        --strands-per-string 12 --orientation V --seconds 20

    python code_matrix.py --fpp http://fpp.local --model Matrix --scroll \
        --text "Last Christmas" --strands-per-string 12 --orientation V --seconds 10
"""

from __future__ import annotations

import argparse
import logging
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 6
FONT_WIDTH = 5
FONT_HEIGHT = 7

# 5x7 font, one string per row, "#" = lit pixel. Digits, capital letters
# (text is shown in capitals) and a little punctuation.
FONT: Dict[str, Tuple[str, ...]] = {
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": (".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "\u00c4": ("#...#", ".###.", "#...#", "#...#", "#####", "#...#", "#...#"),
    "\u00d6": ("#...#", ".###.", "#...#", "#...#", "#...#", "#...#", ".###."),
    "\u00dc": ("#...#", ".....", "#...#", "#...#", "#...#", "#...#", ".###."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    "-": (".....", ".....", ".....", ".###.", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ",": (".....", ".....", ".....", ".....", ".##..", "..#..", ".#..."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    "(": ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ")": (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    "&": (".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"),
    ":": (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    "/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    "+": (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
}

# Scrolling text: how many characters should at least be visible at once.
SCROLL_MIN_VISIBLE_CHARS = 3
SCROLL_MIN_SPEED = 25.0   # pixels per second: slower looks stuck
SCROLL_MAX_SPEED = 70.0   # faster cannot be read
SCROLL_FPS = 15

# Scrolling text drawn by FPP itself (overlay effect "Text", FPP 7+): FPP moves
# it one pixel at a time on its own clock, so it runs smoothly whatever the
# network does. The width of the rendered text is only known to FPP, so the
# speed is fitted with an estimate of the average letter width.
NATIVE_TEXT_FONT = "FreeSansBold"
NATIVE_CHAR_WIDTH = 0.5   # measured on FPP 10 with FreeSansBold: 0.47–0.49 points per letter
NATIVE_FONT_FILL = 0.96   # font points per matrix row: capitals plus descenders just fit


class NativeTextUnsupported(Exception):
    """FPP has no overlay text effect (or rejected the command)."""


def native_font_size(height: int) -> int:
    return max(4, min(100, round(height * NATIVE_FONT_FILL)))


def native_scroll_speed(text: str, width: int, font_size: int, seconds: float) -> int:
    """Pixels per second so that one pass of ``text`` takes about ``seconds``."""
    text_width = len(text) * font_size * NATIVE_CHAR_WIDTH
    speed = (width + text_width) / max(1.0, seconds)
    return int(round(max(SCROLL_MIN_SPEED, min(SCROLL_MAX_SPEED, speed))))


@dataclass(frozen=True)
class Wiring:
    """How the nodes of a matrix are laid out (same terms as FPP / xLights)."""

    node_count: int
    strings: int
    strands_per_string: int
    vertical: bool
    start_corner: str  # "TL", "TR", "BL", "BR"

    @property
    def strand_count(self) -> int:
        return max(1, self.strings * self.strands_per_string)

    @property
    def strand_length(self) -> int:
        return max(1, self.node_count // self.strand_count)

    @property
    def width(self) -> int:
        return self.strand_count if self.vertical else self.strand_length

    @property
    def height(self) -> int:
        return self.strand_length if self.vertical else self.strand_count


def build_node_map(wiring: Wiring) -> List[int]:
    """Return ``map[y * width + x] = node index`` for a wiring.

    This mirrors FPP's PixelOverlayModel channel map (strands zig-zag inside a
    string, every string starts again at the start side), so the same function
    describes both the real matrix and the model as FPP sees it.
    """
    width, height = wiring.width, wiring.height
    top_to_bottom = not wiring.start_corner.upper().startswith("B")
    left_to_right = not wiring.start_corner.upper().endswith("R")
    sps = max(1, wiring.strands_per_string)
    node_map = [0] * (width * height)

    for y in range(height):
        for x in range(width):
            if wiring.vertical:
                segment = x % sps
                out_x = x if left_to_right else width - x - 1
                out_y = height - y - 1 if top_to_bottom == bool(segment % 2) else y
                node = out_x * height + out_y
            else:
                segment = y % sps
                out_x = width - x - 1 if left_to_right == bool(segment % 2) else x
                out_y = y if top_to_bottom else height - y - 1
                node = out_y * width + out_x
            node_map[y * width + x] = node
    return node_map


def prepare_text(text: str) -> str:
    """Reduce any text to what the font can show: capitals, umlauts kept,
    other accents dropped, unknown characters (emoji ...) removed."""
    out: List[str] = []
    for char in str(text or "").upper().replace("\u1e9e", "SS").replace("\u00df", "SS"):
        if char not in FONT:
            # e.g. "\u00c9" -> "E"; typographic quotes and dashes -> plain ones
            char = {"\u2019": "'", "\u2018": "'", "`": "'", "\u2013": "-", "\u2014": "-", "_": " "}.get(char, char)
            if char not in FONT:
                char = unicodedata.normalize("NFKD", char)[:1]
        if char in FONT:
            out.append(char)
        elif char.isspace():
            out.append(" ")
    return " ".join("".join(out).split())


def scroll_scale(width: int, height: int) -> int:
    """Largest font scale that still shows a few characters at once."""
    scale = 1
    for candidate in range(2, 64):
        if FONT_HEIGHT * candidate > height:
            break
        if width // ((FONT_WIDTH + 1) * candidate) < SCROLL_MIN_VISIBLE_CHARS:
            break
        scale = candidate
    return scale


def render_strip(text: str, scale: int = 1) -> List[List[bool]]:
    """Render one line of text as ``rows[y][x]``, as wide as the text needs."""
    chars = [c for c in prepare_text(text) if c in FONT]
    if not chars:
        raise ValueError("Nothing to render.")
    pitch = (FONT_WIDTH + 1) * scale
    strip_width = len(chars) * pitch - scale
    rows = [[False] * strip_width for _ in range(FONT_HEIGHT * scale)]
    for index, char in enumerate(chars):
        for gy, glyph_row in enumerate(FONT[char]):
            for gx, cell in enumerate(glyph_row):
                if cell != "#":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        rows[gy * scale + dy][index * pitch + gx * scale + dx] = True
    return rows


def scroll_window(strip: List[List[bool]], width: int, height: int, offset: int) -> List[List[bool]]:
    """One frame of a strip moving right to left, vertically centred.

    ``offset`` 0 = the text is just outside on the right; one full pass takes
    ``width + strip width`` steps, further offsets start the next pass.
    """
    strip_width = len(strip[0])
    offset %= width + strip_width
    top = max(0, (height - len(strip)) // 2)
    rows = [[False] * width for _ in range(height)]
    for sy, strip_row in enumerate(strip):
        y = top + sy
        if y >= height:
            break
        row = rows[y]
        for x in range(width):
            sx = x + offset - width
            if 0 <= sx < strip_width and strip_row[sx]:
                row[x] = True
    return rows


def render_text(text: str, width: int, height: int) -> List[List[bool]]:
    """Render a short text (the code) as large as it fits, centred, as ``rows[y][x]``.

    Raises ``ValueError`` if the text does not fit even at scale 1.
    """
    chars = [c for c in text if c in FONT]
    if not chars:
        raise ValueError("Nothing to render.")

    scale = 0
    for candidate in range(1, 64):
        gap = candidate
        needed_w = len(chars) * FONT_WIDTH * candidate + (len(chars) - 1) * gap
        needed_h = FONT_HEIGHT * candidate
        if needed_w > width or needed_h > height:
            break
        scale = candidate
    if scale == 0:
        raise ValueError(f"{len(chars)} characters do not fit on a {width}x{height} matrix.")

    gap = scale
    total_w = len(chars) * FONT_WIDTH * scale + (len(chars) - 1) * gap
    total_h = FONT_HEIGHT * scale
    left = (width - total_w) // 2
    top = (height - total_h) // 2

    rows = [[False] * width for _ in range(height)]
    for index, char in enumerate(chars):
        glyph = FONT[char]
        origin_x = left + index * (FONT_WIDTH * scale + gap)
        for gy, glyph_row in enumerate(glyph):
            for gx, cell in enumerate(glyph_row):
                if cell != "#":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        rows[top + gy * scale + dy][origin_x + gx * scale + dx] = True
    return rows


def frames_due(elapsed: float) -> int:
    """Number of whole frame slots that have passed after ``elapsed`` seconds."""
    return int(elapsed * SCROLL_FPS)


def parse_color(value: str, default: Tuple[int, int, int] = (255, 255, 255)) -> Tuple[int, int, int]:
    """Parse ``#RRGGBB`` or ``R,G,B``."""
    text = (value or "").strip()
    try:
        if text.startswith("#") and len(text) == 7:
            return (int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16))
        parts = [int(p) for p in text.split(",")]
        if len(parts) == 3 and all(0 <= p <= 255 for p in parts):
            return (parts[0], parts[1], parts[2])
    except ValueError:
        pass
    return default


class CodeMatrix:
    """Draws a code on one FPP overlay model and removes it again."""

    def __init__(
        self,
        fpp_base_url: str,
        model: str,
        color: Tuple[int, int, int] = (255, 255, 255),
        strings: Optional[int] = None,
        strands_per_string: Optional[int] = None,
        orientation: Optional[str] = None,
        start_corner: Optional[str] = None,
    ) -> None:
        self.base = fpp_base_url.rstrip("/")
        self.model = model
        self.color = color
        self._strings = strings
        self._strands_per_string = strands_per_string
        self._orientation = orientation
        self._start_corner = start_corner
        self._model_info: Optional[Dict[str, Any]] = None
        self._model_info_at = 0.0
        self._bulk_supported = True

    # -- FPP access -------------------------------------------------------
    def _url(self, suffix: str = "") -> str:
        return f"{self.base}/api/overlays/model/{requests.utils.quote(self.model, safe='')}{suffix}"

    def model_info(self, max_age: float = 300) -> Dict[str, Any]:
        """Model description from FPP (cached)."""
        if self._model_info is None or time.monotonic() - self._model_info_at > max_age:
            resp = requests.get(self._url(), timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            info = resp.json()
            if not isinstance(info, dict) or not info.get("ChannelCount"):
                raise ValueError(f"Overlay model '{self.model}' not found on FPP.")
            self._model_info = info
            self._model_info_at = time.monotonic()
        return self._model_info

    def _wirings(self) -> Tuple[Wiring, Wiring]:
        """Return (real wiring, wiring as FPP sees the model)."""
        info = self.model_info()
        node_count = int(info["ChannelCount"]) // max(1, int(info.get("ChannelCountPerNode") or 3))
        fpp = Wiring(
            node_count=node_count,
            strings=max(1, int(info.get("StringCount") or 1)),
            strands_per_string=max(1, int(info.get("StrandsPerString") or 1)),
            vertical=str(info.get("Orientation") or "H").upper().startswith("V"),
            start_corner=str(info.get("StartCorner") or "TL").upper(),
        )
        real = Wiring(
            node_count=node_count,
            strings=self._strings or fpp.strings,
            strands_per_string=self._strands_per_string or fpp.strands_per_string,
            vertical=self._orientation.upper().startswith("V") if self._orientation else fpp.vertical,
            start_corner=(self._start_corner or fpp.start_corner).upper(),
        )
        return real, fpp

    def describe(self) -> str:
        real, fpp = self._wirings()
        return (
            f"model '{self.model}': {real.node_count} nodes, shown as {real.width}x{real.height} "
            f"(FPP describes it as {fpp.width}x{fpp.height})"
        )

    # -- drawing ----------------------------------------------------------
    def _pixel_positions(self) -> Tuple[Wiring, Wiring, List[Optional[int]]]:
        """Return (real wiring, FPP's wiring, ``pos[y * width + x]``): where a
        pixel of the real matrix sits in FPP's own model coordinates."""
        real, fpp = self._wirings()
        position_of_node = {node: pos for pos, node in enumerate(build_node_map(fpp))}
        positions = [position_of_node.get(node) for node in build_node_map(real)]
        return real, fpp, positions

    def _frame(self, text: str) -> Tuple[bytes, List[Tuple[int, int]], int, int]:
        """Build the frame in FPP's own model coordinates.

        Returns (raw RGB bytes, lit (x, y) positions, fpp width, fpp height).
        """
        real, fpp, positions = self._pixel_positions()
        rows = render_text(text, real.width, real.height)

        frame = bytearray(fpp.width * fpp.height * 3)
        lit: List[Tuple[int, int]] = []
        for y, row in enumerate(rows):
            for x, on in enumerate(row):
                if not on:
                    continue
                pos = positions[y * real.width + x]
                if pos is None:
                    continue
                frame[pos * 3 : pos * 3 + 3] = bytes(self.color)
                lit.append((pos % fpp.width, pos // fpp.width))
        return bytes(frame), lit, fpp.width, fpp.height

    def _put(self, suffix: str, **kwargs: Any) -> requests.Response:
        return requests.put(self._url(suffix), timeout=REQUEST_TIMEOUT, **kwargs)

    def show(self, text: str) -> None:
        """Display ``text`` (digits) on the model, replacing whatever it shows."""
        frame, lit, _, _ = self._frame(text)

        drawn = False
        if self._bulk_supported:
            resp = self._put("/data", data=frame, headers={"Content-Type": "application/octet-stream"})
            if resp.ok:
                drawn = True
            elif resp.status_code in (400, 404, 405, 500, 501):
                # Older FPP without the bulk endpoint: fall back to single pixels.
                logger.info("FPP bulk overlay write not available (HTTP %s), using pixel writes.", resp.status_code)
                self._bulk_supported = False
            else:
                resp.raise_for_status()
        if not drawn:
            self._put("/fill", json={"RGB": [0, 0, 0]}).raise_for_status()
            for x, y in lit:
                self._put("/pixel", json={"X": x, "Y": y, "RGB": list(self.color)}).raise_for_status()

        # 1 = enabled (opaque): the code replaces e.g. a background effect on this model.
        self._put("/state", json={"State": 1}).raise_for_status()

    def scroll(
        self,
        text: str,
        seconds: float,
        color: Optional[Tuple[int, int, int]] = None,
        speed: Optional[float] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> int:
        """Run ``text`` right to left across the model for ``seconds``, then
        give the model back. Blocks; returns the number of frames sent.

        Without ``speed`` (pixels per second) one pass is fitted into the
        available time, within readable limits; a short text repeats. The
        position follows the clock, so a slow connection to FPP skips frames
        instead of slowing the text down.
        """
        real, fpp, positions = self._pixel_positions()
        strip = render_strip(text, scroll_scale(real.width, real.height))
        pass_length = real.width + len(strip[0])
        if speed is None:
            speed = pass_length / max(1.0, seconds)
        speed = max(SCROLL_MIN_SPEED, min(SCROLL_MAX_SPEED, speed))
        rgb = bytes(color or self.color)
        frame_size = fpp.width * fpp.height * 3
        url = self._url("/data")
        headers = {"Content-Type": "application/octet-stream"}

        frames = 0
        last_offset = -1
        started = time.monotonic()
        session = requests.Session()
        try:
            while True:
                elapsed = time.monotonic() - started
                if elapsed >= seconds or (should_stop is not None and should_stop()):
                    break
                offset = int(elapsed * speed)
                if offset != last_offset:
                    last_offset = offset
                    rows = scroll_window(strip, real.width, real.height, offset)
                    frame = bytearray(frame_size)
                    for y, row in enumerate(rows):
                        base = y * real.width
                        for x, on in enumerate(row):
                            if on:
                                pos = positions[base + x]
                                if pos is not None:
                                    frame[pos * 3 : pos * 3 + 3] = rgb
                    session.put(url, data=bytes(frame), headers=headers, timeout=REQUEST_TIMEOUT).raise_for_status()
                    if frames == 0:
                        # 1 = enabled (opaque): the text replaces the sequence on this model.
                        session.put(self._url("/state"), json={"State": 1}, timeout=REQUEST_TIMEOUT).raise_for_status()
                    frames += 1
                wait = started + (frames_due(elapsed) + 1) / SCROLL_FPS - time.monotonic()
                if wait > 0:
                    time.sleep(min(wait, 1.0 / SCROLL_FPS))
        finally:
            session.close()
            self.hide()
        return frames

    def _overlay_command(self, *args: str) -> requests.Response:
        return requests.post(
            f"{self.base}/api/command",
            json={"command": "Overlay Model Effect", "args": [self.model, *args]},
            timeout=REQUEST_TIMEOUT,
        )

    def scroll_native(
        self,
        text: str,
        seconds: float,
        color: Optional[Tuple[int, int, int]] = None,
        font: str = NATIVE_TEXT_FONT,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> int:
        """Let FPP run ``text`` right to left across the model, once, then give
        the model back after ``seconds`` at the latest. Blocks; returns the
        speed in pixels per second.

        Raises ``NativeTextUnsupported`` if FPP does not know the effect.
        """
        info = self.model_info()
        real, fpp = self._wirings()
        width = int(info.get("width") or fpp.width)
        height = int(info.get("height") or fpp.height)
        size = native_font_size(height)
        message = " ".join(str(text).split())
        speed = native_scroll_speed(message, width, size, seconds)
        r, g, b = color or self.color
        resp = self._overlay_command(
            "Enabled", "Text", f"#{r:02X}{g:02X}{b:02X}", font, str(size), "true",
            "Right to Left", str(speed), "0", message,
        )
        if resp.status_code in (400, 404, 500, 501) or "Started" not in resp.text:
            raise NativeTextUnsupported(f"HTTP {resp.status_code}: {resp.text[:120]}")
        resp.raise_for_status()
        started = time.monotonic()
        try:
            while time.monotonic() - started < seconds:
                if should_stop is not None and should_stop():
                    break
                time.sleep(0.1)
        finally:
            # Stops a text still running (a long title or a cancelled one);
            # one that already scrolled off has switched the model off itself.
            try:
                self._overlay_command("False", "Stop Effects")
            except requests.RequestException:
                pass
            self.hide()
        return speed

    def hide(self) -> None:
        """Give the model back to sequences/effects."""
        self._put("/state", json={"State": 0}).raise_for_status()
        try:
            self._put("/fill", json={"RGB": [0, 0, 0]})
        except requests.RequestException:
            pass


def _main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Test: show digits or a scrolling text on an FPP overlay model.")
    parser.add_argument("--fpp", required=True, help="FPP base URL, e.g. http://fpp.local")
    parser.add_argument("--model", required=True, help="Overlay model name, e.g. Matrix")
    parser.add_argument("--text", default="123", help="Digits to show, or any text with --scroll")
    parser.add_argument("--scroll", action="store_true", help="Run the text across the matrix as scrolling text")
    parser.add_argument("--speed", type=float, help="Scrolling speed in pixels per second (default: fitted to --seconds)")
    parser.add_argument("--color", default="#FFFFFF")
    parser.add_argument("--strings", type=int)
    parser.add_argument("--strands-per-string", type=int)
    parser.add_argument("--orientation", choices=["H", "V"])
    parser.add_argument("--start-corner", choices=["TL", "TR", "BL", "BR"])
    parser.add_argument("--seconds", type=float, default=20, help="How long to show it")
    parser.add_argument("--dry-run", action="store_true", help="Only print the picture, do not touch the lights")
    args = parser.parse_args(argv)

    matrix = CodeMatrix(
        args.fpp, args.model, parse_color(args.color),
        strings=args.strings, strands_per_string=args.strands_per_string,
        orientation=args.orientation, start_corner=args.start_corner,
    )
    print(matrix.describe())
    real, _ = matrix._wirings()
    if args.scroll:
        scale = scroll_scale(real.width, real.height)
        strip = render_strip(args.text, scale)
        print(f"Scrolling text '{prepare_text(args.text)}': letters {FONT_HEIGHT * scale} pixels high, "
              f"{len(strip[0])} pixels long")
        # Preview: the moment the beginning of the text has reached the left edge.
        for row in scroll_window(strip, real.width, real.height, real.width):
            print("".join("#" if on else "." for on in row))
        if args.dry_run:
            return 0
        started = time.monotonic()
        frames = matrix.scroll(args.text, args.seconds, speed=args.speed)
        took = time.monotonic() - started
        print(f"{frames} frames in {took:.1f}s ({frames / max(took, 0.1):.1f} per second), hidden again.")
        return 0

    for row in render_text(args.text, real.width, real.height):
        print("".join("#" if on else "." for on in row))
    if args.dry_run:
        return 0

    matrix.show(args.text)
    print(f"Showing '{args.text}' for {args.seconds:.0f}s ...")
    try:
        time.sleep(args.seconds)
    finally:
        matrix.hide()
        print("Hidden again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
