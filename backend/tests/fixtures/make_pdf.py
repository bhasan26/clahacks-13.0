"""
Simple valid PDF generator for test fixtures without heavy external dependencies.
Produces valid PDF 1.4 documents with selectable text.
"""

def create_simple_pdf(text_lines: list[str]) -> bytes:
    """Generates a valid, readable PDF 1.4 containing the provided lines of text."""
    # Build text stream
    stream_content = "BT\n/F1 11 Tf\n50 720 Td\n16 TL\n"
    for line in text_lines:
        line_clean = line.replace("—", "--").replace("–", "-").replace(""", '"').replace(""", '"').replace("'", "'")
        safe_line = line_clean.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if line.startswith("# "):
            stream_content += f"/F1 16 Tf\n({safe_line[2:]}) Tj\nT*\n/F1 11 Tf\n"
        elif line.startswith("## "):
            stream_content += f"/F1 13 Tf\n({safe_line[3:]}) Tj\nT*\n/F1 11 Tf\n"
        else:
            stream_content += f"({safe_line}) Tj\nT*\n"
    stream_content += "ET\n"
    stream_bytes = stream_content.encode("latin-1", errors="replace")

    # Assemble PDF objects
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    )
    obj4 = (
        f"4 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode("latin-1")
        + stream_bytes
        + b"\nendstream\nendobj\n"
    )
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"

    header = b"%PDF-1.4\n"
    body = header
    offsets = [0]

    for obj in [obj1, obj2, obj3, obj4, obj5]:
        offsets.append(len(body))
        body += obj

    xref_offset = len(body)
    xref = f"xref\n0 6\n0000000000 65535 f \n".encode("latin-1")
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n".encode("latin-1")

    trailer = (
        f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1")
    )

    return body + xref + trailer
