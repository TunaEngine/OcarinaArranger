"""Low-level PDF writing utilities used by the exporter."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .layouts import PdfLayout


@dataclass(frozen=True)
class LinkAnnotation:
    rect: Tuple[float, float, float, float]
    uri: str


class PageBuilder:
    def __init__(self, layout: PdfLayout) -> None:
        self.layout = layout
        self._commands: List[str] = []
        self._annotations: List[LinkAnnotation] = []

    def draw_text(
        self,
        x: float,
        y: float,
        text: str,
        *,
        size: Optional[float] = None,
        font: str = "F1",
        angle: float = 0.0,
        fill_gray: float = 0.0,
        fill_rgb: Optional[Tuple[float, float, float]] = None,
    ) -> None:
        if size is None:
            size = self.layout.font_size
        baseline = self.layout.height - y
        escaped = _escape_text(text)
        if abs(angle) <= 1e-6:
            a, b, c, d = 1.0, 0.0, 0.0, 1.0
        else:
            radians = math.radians(angle)
            cos_theta = math.cos(radians)
            sin_theta = math.sin(radians)
            if abs(cos_theta) < 1e-6:
                cos_theta = 0.0
            if abs(sin_theta) < 1e-6:
                sin_theta = 0.0
            a, b = cos_theta, sin_theta
            c, d = -sin_theta, cos_theta
        if fill_rgb is not None:
            color_command = f"{fill_rgb[0]:.3f} {fill_rgb[1]:.3f} {fill_rgb[2]:.3f} rg"
        else:
            color_command = f"{fill_gray:.3f} g"

        self._commands.extend(
            [
                "q",
                color_command,
                "BT",
                f"/{font} {size:.2f} Tf",
                f"{a:.2f} {b:.2f} {c:.2f} {d:.2f} {x:.2f} {baseline:.2f} Tm",
                f"({escaped}) Tj",
                "ET",
                "Q",
            ]
        )

    def estimate_text_width(
        self,
        text: str,
        *,
        size: Optional[float] = None,
        font: str = "F1",
    ) -> float:
        if size is None:
            size = self.layout.font_size
        if not text:
            return 0.0
        if font == "F2":
            average_width = size * 0.6
        else:
            average_width = size * 0.55
        return len(text) * average_width

    def add_link_annotation(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        uri: str,
    ) -> None:
        if width <= 0 or height <= 0 or not uri:
            return
        lower_left_y = self.layout.height - (y + height)
        upper_right_y = self.layout.height - y
        y1 = min(lower_left_y, upper_right_y)
        y2 = max(lower_left_y, upper_right_y)
        rect = (x, y1, x + width, y2)
        self._annotations.append(LinkAnnotation(rect=rect, uri=uri))

    @property
    def link_annotations(self) -> Sequence[LinkAnnotation]:
        return tuple(self._annotations)

    def draw_line(self, x1: float, y1: float, x2: float, y2: float, *, gray: float = 0.0, line_width: float = 1.0) -> None:
        px1, py1 = self._to_pdf_point(x1, y1)
        px2, py2 = self._to_pdf_point(x2, y2)
        self._commands.extend(
            [
                "q",
                f"{gray:.3f} G",
                f"{line_width:.2f} w",
                f"{px1:.2f} {py1:.2f} m",
                f"{px2:.2f} {py2:.2f} l",
                "S",
                "Q",
            ]
        )

    def draw_rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        fill_gray: Optional[float] = None,
        stroke_gray: Optional[float] = None,
        line_width: float = 1.0,
    ) -> None:
        if width <= 0 or height <= 0:
            return
        px, py = self._to_pdf_rect(x, y, height)
        commands = ["q"]
        if stroke_gray is not None:
            commands.append(f"{stroke_gray:.3f} G")
            commands.append(f"{line_width:.2f} w")
        if fill_gray is not None:
            commands.append(f"{fill_gray:.3f} g")
        commands.append(f"{px:.2f} {py:.2f} {width:.2f} {height:.2f} re")
        if fill_gray is not None and stroke_gray is not None:
            commands.append("B")
        elif fill_gray is not None:
            commands.append("f")
        elif stroke_gray is not None:
            commands.append("S")
        else:
            commands.append("n")
        commands.append("Q")
        self._commands.extend(commands)

    def draw_circle(
        self,
        cx: float,
        cy: float,
        radius: float,
        *,
        fill_gray: Optional[float] = None,
        stroke_gray: Optional[float] = 0.0,
        line_width: float = 1.0,
    ) -> None:
        if radius <= 0:
            return
        cx_pdf, cy_pdf = self._to_pdf_point(cx, cy)
        k = radius * 0.5522847498307936
        commands = ["q"]
        if stroke_gray is not None:
            commands.append(f"{stroke_gray:.3f} G")
            commands.append(f"{line_width:.2f} w")
        if fill_gray is not None:
            commands.append(f"{fill_gray:.3f} g")
        commands.extend(
            [
                f"{cx_pdf + radius:.2f} {cy_pdf:.2f} m",
                f"{cx_pdf + radius:.2f} {cy_pdf + k:.2f} {cx_pdf + k:.2f} {cy_pdf + radius:.2f} {cx_pdf:.2f} {cy_pdf + radius:.2f} c",
                f"{cx_pdf - k:.2f} {cy_pdf + radius:.2f} {cx_pdf - radius:.2f} {cy_pdf + k:.2f} {cx_pdf - radius:.2f} {cy_pdf:.2f} c",
                f"{cx_pdf - radius:.2f} {cy_pdf - k:.2f} {cx_pdf - k:.2f} {cy_pdf - radius:.2f} {cx_pdf:.2f} {cy_pdf - radius:.2f} c",
                f"{cx_pdf + k:.2f} {cy_pdf - radius:.2f} {cx_pdf + radius:.2f} {cy_pdf - k:.2f} {cx_pdf + radius:.2f} {cy_pdf:.2f} c",
            ]
        )
        if fill_gray is not None and stroke_gray is not None:
            commands.append("B")
        elif fill_gray is not None:
            commands.append("f")
        elif stroke_gray is not None:
            commands.append("S")
        else:
            commands.append("n")
        commands.append("Q")
        self._commands.extend(commands)

    def draw_oval(
        self,
        cx: float,
        cy: float,
        rx: float,
        ry: float,
        *,
        fill_gray: Optional[float] = None,
        stroke_gray: Optional[float] = 0.0,
        line_width: float = 1.0,
    ) -> None:
        if rx <= 0 or ry <= 0:
            return
        cx_pdf, cy_pdf = self._to_pdf_point(cx, cy)
        kx = rx * 0.5522847498307936
        ky = ry * 0.5522847498307936
        commands = ["q"]
        if stroke_gray is not None:
            commands.append(f"{stroke_gray:.3f} G")
            commands.append(f"{line_width:.2f} w")
        if fill_gray is not None:
            commands.append(f"{fill_gray:.3f} g")
        commands.extend(
            [
                f"{cx_pdf + rx:.2f} {cy_pdf:.2f} m",
                f"{cx_pdf + rx:.2f} {cy_pdf + ky:.2f} {cx_pdf + kx:.2f} {cy_pdf + ry:.2f} {cx_pdf:.2f} {cy_pdf + ry:.2f} c",
                f"{cx_pdf - kx:.2f} {cy_pdf + ry:.2f} {cx_pdf - rx:.2f} {cy_pdf + ky:.2f} {cx_pdf - rx:.2f} {cy_pdf:.2f} c",
                f"{cx_pdf - rx:.2f} {cy_pdf - ky:.2f} {cx_pdf - kx:.2f} {cy_pdf - ry:.2f} {cx_pdf:.2f} {cy_pdf - ry:.2f} c",
                f"{cx_pdf + kx:.2f} {cy_pdf - ry:.2f} {cx_pdf + rx:.2f} {cy_pdf - ky:.2f} {cx_pdf + rx:.2f} {cy_pdf:.2f} c",
            ]
        )
        if fill_gray is not None and stroke_gray is not None:
            commands.append("B")
        elif fill_gray is not None:
            commands.append("f")
        elif stroke_gray is not None:
            commands.append("S")
        else:
            commands.append("n")
        commands.append("Q")
        self._commands.extend(commands)

    def fill_half_circle(self, cx: float, cy: float, radius: float, *, fill_gray: float) -> None:
        if radius <= 0:
            return
        cx_pdf, cy_pdf = self._to_pdf_point(cx, cy)
        k = radius * 0.5522847498307936
        commands = [
            "q",
            f"{fill_gray:.3f} g",
            f"{cx_pdf:.2f} {cy_pdf + radius:.2f} m",
            f"{cx_pdf - k:.2f} {cy_pdf + radius:.2f} {cx_pdf - radius:.2f} {cy_pdf + k:.2f} {cx_pdf - radius:.2f} {cy_pdf:.2f} c",
            f"{cx_pdf - radius:.2f} {cy_pdf - k:.2f} {cx_pdf - k:.2f} {cy_pdf - radius:.2f} {cx_pdf:.2f} {cy_pdf - radius:.2f} c",
            "h",
            "f",
            "Q",
        ]
        self._commands.extend(commands)

    def draw_polygon(
        self,
        points: Sequence[Tuple[float, float]],
        *,
        fill_gray: Optional[float] = None,
        stroke_gray: Optional[float] = 0.0,
        close: bool = True,
        line_width: float = 1.0,
    ) -> None:
        if len(points) < 2:
            return
        commands = ["q"]
        if stroke_gray is not None:
            commands.append(f"{stroke_gray:.3f} G")
            commands.append(f"{line_width:.2f} w")
        if fill_gray is not None:
            commands.append(f"{fill_gray:.3f} g")
        start_x, start_y = self._to_pdf_point(*points[0])
        commands.append(f"{start_x:.2f} {start_y:.2f} m")
        for x, y in points[1:]:
            px, py = self._to_pdf_point(x, y)
            commands.append(f"{px:.2f} {py:.2f} l")
        if close:
            commands.append("h")
        if fill_gray is not None and stroke_gray is not None:
            commands.append("B")
        elif fill_gray is not None:
            commands.append("f")
        elif stroke_gray is not None:
            commands.append("S")
        else:
            commands.append("n")
        commands.append("Q")
        self._commands.extend(commands)

    def build_stream(self) -> bytes:
        content = "\n".join(self._commands).encode("latin-1")
        return _encode_stream(content)

    def _to_pdf_point(self, x: float, y: float) -> Tuple[float, float]:
        return (x, self.layout.height - y)

    def _to_pdf_rect(self, x: float, y: float, height: float) -> Tuple[float, float]:
        return (x, self.layout.height - (y + height))


class PdfWriter:
    def __init__(self, layout: PdfLayout) -> None:
        self._layout = layout
        self._pages: List[PageBuilder] = []

    def add_page(self, page: PageBuilder) -> None:
        self._pages.append(page)

    def write(self, output_path: Path) -> None:
        pages = self._pages or [PageBuilder(self._layout)]

        objects: Dict[int, bytes] = {}
        page_objects: List[Tuple[int, bytes]] = []
        content_objects: List[Tuple[int, bytes]] = []
        annotation_objects: List[Tuple[int, bytes]] = []

        font_specs = {"F1": "/Helvetica", "F2": "/Courier"}
        font_numbers: Dict[str, int] = {}
        next_object = 3

        for name, base_font in font_specs.items():
            font_numbers[name] = next_object
            objects[next_object] = _encode(
                f"<< /Type /Font /Subtype /Type1 /BaseFont {base_font} >>"
            )
            next_object += 1

        for page in pages:
            page_obj_num = next_object
            next_object += 1
            content_obj_num = next_object
            next_object += 1
            content_stream = page.build_stream()
            content_objects.append((content_obj_num, content_stream))
            font_entries = " ".join(
                f"/{font} {obj} 0 R" for font, obj in font_numbers.items()
            )
            annotation_refs: List[str] = []
            for annotation in page.link_annotations:
                annot_obj_num = next_object
                next_object += 1
                annotation_refs.append(f"{annot_obj_num} 0 R")
                annotation_objects.append(
                    (
                        annot_obj_num,
                        _encode(_encode_link_annotation(annotation)),
                    )
                )
            annots_clause = ""
            if annotation_refs:
                refs = " ".join(annotation_refs)
                annots_clause = f" /Annots [{refs}]"
            page_objects.append(
                (
                    page_obj_num,
                    _encode(
                        "<< /Type /Page /Parent 2 0 R /Resources << /Font << "
                        f"{font_entries} >> >> "
                        f"/MediaBox [0 0 {self._layout.width:.2f} {self._layout.height:.2f}] "
                        f"/Contents {content_obj_num} 0 R{annots_clause} >>"
                    ),
                )
            )

        kids = " ".join(f"{num} 0 R" for num, _ in page_objects) or ""
        objects[1] = _encode("<< /Type /Catalog /Pages 2 0 R >>")
        objects[2] = _encode(
            f"<< /Type /Pages /Kids [{kids}] /Count {len(page_objects)} >>"
        )
        for num, data in page_objects:
            objects[num] = data
        for num, data in content_objects:
            objects[num] = data
        for num, data in annotation_objects:
            objects[num] = data

        max_obj = max(objects) if objects else 3
        offsets = [0] * (max_obj + 1)
        buffer = bytearray()
        buffer.extend(b"%PDF-1.4\n")

        for obj_num in range(1, max_obj + 1):
            data = objects.get(obj_num)
            if data is None:
                continue
            offsets[obj_num] = len(buffer)
            buffer.extend(_encode(f"{obj_num} 0 obj"))
            buffer.extend(data)
            if not data.endswith(b"\n"):
                buffer.extend(b"\n")
            buffer.extend(b"endobj\n")

        xref_offset = len(buffer)
        buffer.extend(_encode(f"xref\n0 {max_obj + 1}"))
        buffer.extend(b"0000000000 65535 f \n")
        for obj_num in range(1, max_obj + 1):
            offset = offsets[obj_num]
            if offset == 0:
                buffer.extend(b"0000000000 65535 f \n")
            else:
                buffer.extend(_encode(f"{offset:010d} 00000 n "))
                buffer.extend(b"\n")
        buffer.extend(
            _encode(
                f"trailer << /Size {max_obj + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
            )
        )

        output_path.write_bytes(buffer)


def _encode(text: str) -> bytes:
    return (text + "\n").encode("latin-1")


def _encode_stream(content: bytes) -> bytes:
    return _encode(f"<< /Length {len(content)} >>") + b"stream\n" + content + b"\nendstream\n"


def _escape_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _encode_link_annotation(annotation: LinkAnnotation) -> str:
    rect_values = " ".join(f"{value:.2f}" for value in annotation.rect)
    uri = _escape_text(annotation.uri)
    return (
        "<< /Type /Annot /Subtype /Link "
        f"/Rect [{rect_values}] "
        "/Border [0 0 0] /C [0 0 1] "
        f"/A << /S /URI /URI ({uri}) >> >>"
    )


__all__ = ["LinkAnnotation", "PageBuilder", "PdfWriter"]
