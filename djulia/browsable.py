"""A DRF-style browsable HTML view, served by content negotiation.

When a browser (Accept: text/html) hits an endpoint, responses render as a
navigable HTML page with clickable links instead of raw JSON. API clients that
send ``application/vnd.api+json`` still get JSON. Force either with ?format=.
"""
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.utils.html import escape

from .conf import get_setting
from .errors import MEDIA_TYPE

_CSS = (
    "body{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;margin:0;"
    "background:#0d1117;color:#c9d1d9;font-size:13px;line-height:1.6}"
    "header{background:#161b22;padding:12px 20px;border-bottom:1px solid #30363d;"
    "position:sticky;top:0}"
    ".method{background:#238636;color:#fff;padding:2px 8px;border-radius:4px;font-weight:600}"
    "header code{color:#58a6ff;margin-left:8px}"
    "header .raw{float:right;color:#8b949e}"
    "main{padding:20px}"
    ".obj,.arr{border-left:1px solid #30363d;margin-left:8px;padding-left:14px}"
    ".row{white-space:pre-wrap}.item{border-top:1px dashed #21262d}"
    ".key{color:#79c0ff}.str{color:#a5d6ff}.bool{color:#ffa657}.muted{color:#6e7681}"
    "a{color:#58a6ff}details{margin-top:24px}summary{cursor:pointer;color:#8b949e}"
    "pre{background:#161b22;padding:16px;border-radius:6px;overflow:auto}"
)


def prefers_html(request):
    if not get_setting("BROWSABLE"):
        return False
    fmt = request.GET.get("format")
    if fmt == "json":
        return False
    if fmt == "html":
        return True
    accept = request.META.get("HTTP_ACCEPT", "")
    return "text/html" in accept and MEDIA_TYPE not in accept


def render_html(request, document, status=200):
    raw = escape(json.dumps(document, indent=2, cls=DjangoJSONEncoder))
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(request.path)}</title><style>{_CSS}</style></head><body>
<header><span class="method">{escape(request.method)}</span>
<code>{escape(request.get_full_path())}</code>
<a class="raw" href="?format=json">raw json &rarr;</a></header>
<main>{_render(document)}</main>
<details><summary>Raw JSON</summary><pre>{raw}</pre></details>
</body></html>"""
    return HttpResponse(html, status=status, content_type="text/html; charset=utf-8")


def _render(value):
    if isinstance(value, dict):
        rows = "".join(
            f'<div class="row"><span class="key">{escape(k)}</span>: {_render(v)}</div>'
            for k, v in value.items())
        return f'<div class="obj">{rows}</div>'
    if isinstance(value, list):
        if not value:
            return '<span class="muted">[]</span>'
        return '<div class="arr">' + "".join(
            f'<div class="item">{_render(v)}</div>' for v in value) + "</div>"
    if value is None:
        return '<span class="muted">null</span>'
    if isinstance(value, bool):
        return f'<span class="bool">{"true" if value else "false"}</span>'
    if isinstance(value, str) and value.startswith(("http://", "https://", "/")):
        return f'<a href="{escape(value)}">{escape(value)}</a>'
    return f'<span class="str">{escape(str(value))}</span>'
