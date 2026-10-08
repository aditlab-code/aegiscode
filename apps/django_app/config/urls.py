from __future__ import annotations

from django.conf import settings
from django.http import HttpResponseBase
from django.urls import include, path, re_path
from django.views.static import serve


def serve_frontend(request, path, document_root=None) -> HttpResponseBase:
    """Sajikan file frontend production build + header cache yang benar.

    PR-SEC-1: Injeksi ephemeral handshake token ke index.html untuk seamless
    developer authentication tanpa credential login manual.
    """
    clean_path = (path or "").strip()
    if clean_path in ("", "index.html"):
        from pathlib import Path
        from django.http import HttpResponse
        from api.auth import get_ephemeral_token

        index_file = Path(document_root) / "index.html" if document_root else None
        if index_file and index_file.is_file():
            html_text = index_file.read_text(encoding="utf-8")
            token = get_ephemeral_token()
            if token and "</head>" in html_text:
                meta_tag = f'<meta name="aegis-ephemeral-token" content="{token}">\n</head>'
                html_text = html_text.replace("</head>", meta_tag, 1)
            response = HttpResponse(html_text, content_type="text/html; charset=utf-8")
            response["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
            return response

    response = serve(request, path, document_root=document_root)
    if (path or "").startswith("assets/"):
        response["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
    return response


urlpatterns = [
    path("api/", include("api.urls")),
]

# Sajikan frontend production build (bila ada). Tidak mengubah dev (Vite).
if getattr(settings, "FRONTEND_DIST_EXISTS", False):
    _dist = settings.FRONTEND_DIST_DIR
    urlpatterns += [
        # Root "/" menyajikan index.html (entry point Workbench).
        path("", serve_frontend, {"document_root": _dist, "path": "index.html"}),
        re_path(r"^(?P<path>assets/.*)$", serve_frontend, {"document_root": _dist}),
        re_path(r"^(?P<path>favicon\.(?:ico|svg))$", serve_frontend, {"document_root": _dist}),
        re_path(r"^(?P<path>index\.html)$", serve_frontend, {"document_root": _dist}),
    ]
