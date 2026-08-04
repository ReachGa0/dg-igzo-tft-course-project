"""Build the self-contained presentation summary from its XHTML source."""

import base64
import mimetypes
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "report" / "src" / "项目精华版.xhtml"
OUTPUT = ROOT / "report" / "final" / "项目精华版.html"


def embed(match: re.Match[str]) -> str:
    relative = match.group(1)
    image = ROOT / "report" / relative
    mime, _ = mimetypes.guess_type(image.name)
    if not image.is_file() or not mime:
        raise FileNotFoundError(image)
    payload = base64.b64encode(image.read_bytes()).decode("ascii")
    return f'src="data:{mime};base64,{payload}"'


text = SOURCE.read_text(encoding="utf-8")
text = re.sub(r'src="(assets/[^"]+)"', embed, text)
OUTPUT.write_text(text, encoding="utf-8")
print(OUTPUT)
