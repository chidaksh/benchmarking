"""Print values onto one page of a blank IRS form at the positions of its fillable fields."""

import io
import logging

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

logging.disable(logging.CRITICAL)


def text_fields(page, field_type="/Tx"):
    """Return {field name: rectangle} for the text fields (or "/Btn" checkboxes) on a page, in page order."""
    fields = {}
    for annotation in page.get("/Annots") or []:
        annotation = annotation.get_object()
        parent = annotation.get("/Parent").get_object() if annotation.get("/Parent") else {}
        kind = annotation.get("/FT") or parent.get("/FT")
        name = annotation.get("/T") or parent.get("/T")
        if annotation.get("/Subtype") == "/Widget" and kind == field_type and name:
            key = str(name)
            while key in fields:
                key += "'"
            fields[key] = [float(v) for v in annotation["/Rect"]]
    return fields


def stamp_page(source_path, page_number, text_values, target_path, checked_boxes=(), font_size=9):
    """Write one page of the form with values drawn inside its fields, as ordinary page text.

    A field is addressed by its name, or by its position in page order when given a number.
    """
    reader = PdfReader(source_path)
    page = reader.pages[page_number - 1]
    text_rectangles = text_fields(page)
    text_rectangles.update(enumerate(list(text_rectangles.values())))
    box_rectangles = text_fields(page, "/Btn")
    box_rectangles.update(enumerate(list(box_rectangles.values())))
    buffer = io.BytesIO()
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    overlay = canvas.Canvas(buffer, pagesize=(width, height))
    overlay.setFont("Helvetica", font_size)
    for index, text in text_values.items():
        left, bottom, _, top = text_rectangles[index]
        overlay.drawString(left + 2, bottom + max((top - bottom - font_size) / 2, 1) + 1, str(text))
    for index in checked_boxes:
        left, bottom, _, top = box_rectangles[index]
        overlay.drawString(left + 1, bottom + max((top - bottom - font_size) / 2, 1) + 1, "X")
    overlay.save()
    buffer.seek(0)
    writer = PdfWriter()
    page = writer.add_page(page)
    page.merge_page(PdfReader(buffer).pages[0])
    writer.remove_annotations(subtypes="/Widget")
    writer.write(target_path)


if __name__ == "__main__":
    import sys

    # Probe: print each field's position number inside the field, to see where it lands.
    source, page_number, target = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    page = PdfReader(source).pages[page_number - 1]
    count = len(text_fields(page))
    boxes = len(text_fields(page, "/Btn"))
    if len(sys.argv) > 4 and sys.argv[4] == "boxes":
        stamp_page(source, page_number, {}, target, checked_boxes=range(boxes), font_size=7)
    else:
        stamp_page(source, page_number, {index: f"F{index:02d}" for index in range(count)}, target, font_size=7)
    print(count, "text fields,", boxes, "checkboxes")
