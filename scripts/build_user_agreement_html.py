"""Convert Desktop DOCX agreement into miniapp/docs/user-agreement.html."""

from __future__ import annotations

from html import escape
from pathlib import Path

from docx import Document

SRC = Path(r"c:\Users\brett\Desktop\Користувацька угода.docx")
DST = (
    Path(__file__).resolve().parent.parent
    / "miniapp"
    / "docs"
    / "user-agreement.html"
)


def is_section_title(text: str) -> bool:
    if len(text) >= 90:
        return False
    # "1. Терміни", "10. Інтелектуальна власність"
    parts = text.split(".", 1)
    if len(parts) != 2:
        return False
    return parts[0].strip().isdigit() and bool(parts[1].strip())


def main() -> None:
    doc = Document(str(SRC))
    blocks: list[str] = []
    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if not text:
            continue
        if text.startswith("Користувацька угода"):
            blocks.append(f"<h1>{escape(text)}</h1>")
        elif text.startswith("Редакція"):
            blocks.append(f'<p class="meta">{escape(text)}</p>')
        elif is_section_title(text):
            blocks.append(f"<h2>{escape(text)}</h2>")
        elif text.endswith(":") and len(text) < 80:
            blocks.append(f'<p class="lead">{escape(text)}</p>')
        else:
            blocks.append(f"<p>{escape(text)}</p>")

    html = f"""<!DOCTYPE html>
<html lang="uk">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Користувацька угода — KIRS</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      line-height: 1.55;
      color: #1a1a1a;
      background: #f6f7f9;
    }}
    main {{
      max-width: 720px;
      margin: 0 auto;
      padding: 20px 16px 48px;
      background: #fff;
      min-height: 100vh;
      box-sizing: border-box;
    }}
    h1 {{ font-size: 1.35rem; margin: 0 0 8px; line-height: 1.3; }}
    h2 {{ font-size: 1.05rem; margin: 1.4em 0 0.45em; }}
    p {{ margin: 0.45em 0; font-size: 0.95rem; }}
    p.meta {{ color: #666; font-size: 0.88rem; margin-bottom: 1em; }}
    p.lead {{ font-weight: 600; margin-top: 0.7em; }}
    .top {{
      position: sticky;
      top: 0;
      background: #fff;
      padding: 12px 0 10px;
      border-bottom: 1px solid #e8eaed;
      margin: -4px 0 16px;
    }}
    .top a {{ color: #1a5fb4; text-decoration: none; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <main>
    <div class="top"><a href="/" target="_top">← До застосунку</a></div>
{chr(10).join(blocks)}
  </main>
</body>
</html>
"""
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(html, encoding="utf-8")
    print(f"wrote {DST} ({DST.stat().st_size} bytes, {len(blocks)} blocks)")


if __name__ == "__main__":
    main()
