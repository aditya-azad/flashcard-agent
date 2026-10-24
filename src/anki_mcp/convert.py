"""Convert lightweight markdown/LaTeX notation to Anki-native formatting.

Conversions (applied to every Front/Back the server writes to Anki):

- ``$$...$$`` display math  ->  ``\\[...\\]``  (Anki MathJax display)
- ``$...$``   inline math   ->  ``\\(...\\)``  (Anki MathJax inline)
- ``**text**`` markdown bold ->  ``<b>text</b>``

The conversion is idempotent: text that already uses ``\\(...\\)``,
``\\[...\\]`` or ``<b>`` is left unchanged.
"""

import re

_DISPLAY_MATH = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_INLINE_MATH = re.compile(r"(?<!\$)\$(?!\$)((?:\\.|[^$\\])+?)\$(?!\$)")
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)


def to_anki(text: str) -> str:
    """Convert $/$$ math and **bold** to Anki MathJax/HTML formatting."""
    text = _DISPLAY_MATH.sub(lambda m: "\\[" + m.group(1) + "\\]", text)
    text = _INLINE_MATH.sub(lambda m: "\\(" + m.group(1) + "\\)", text)
    text = _BOLD.sub(lambda m: "<b>" + m.group(1) + "</b>", text)
    return text
