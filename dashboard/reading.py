"""Bionic-style text rendering: bold the first part of every word."""
import math
import re

from django.utils.html import escape
from django.utils.safestring import mark_safe

_WORD_SPLIT = re.compile(r'(\w+)', re.UNICODE)
_PARAGRAPH_SPLIT = re.compile(r'\n\s*\n')

MIN_INTENSITY = 0.10
MAX_INTENSITY = 0.90


def clamp_intensity(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.50
    return max(MIN_INTENSITY, min(MAX_INTENSITY, value))


def _bionize_word(word, intensity):
    n = max(1, min(len(word), math.ceil(len(word) * intensity)))
    return f'<b>{escape(word[:n])}</b>{escape(word[n:])}'


def bionize(text, intensity=0.5):
    """Return safe HTML: paragraphs with the leading letters of each word bolded.

    All text is HTML-escaped piece by piece, so uploaded content can never
    inject markup.
    """
    intensity = clamp_intensity(intensity)
    text = text.replace('\r\n', '\n').replace('\r', '\n').strip()
    if not text:
        return mark_safe('')

    paragraphs = []
    for para in _PARAGRAPH_SPLIT.split(text):
        parts = _WORD_SPLIT.split(para)
        html = ''.join(
            _bionize_word(piece, intensity) if i % 2 else escape(piece)
            for i, piece in enumerate(parts)
        )
        paragraphs.append(f'<p>{html.replace(chr(10), "<br>")}</p>')
    return mark_safe('\n'.join(paragraphs))
