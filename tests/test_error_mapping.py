"""Tests for typed error mapping in _handle decorator (AEG-17 / PR-08).

Menguji:
1. FileNotFoundError dan KeyError menghasilkan HTTP 404 not_found.
2. Exception dengan pesan "unknown" (mis. unknown entity/model/task) menghasilkan HTTP 404 not_found, bukan HTTP 400.
3. ValueError dan validation errors menghasilkan HTTP 400 validation_error.
4. GatewayError tetap mempertahankan status_code terstrukturnya.
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path

import pytest

django_dir = Path(__file__).resolve().parent.parent / "apps" / "django_app"
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(django_dir) not in sys.path:
    sys.path.insert(0, str(django_dir))
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
try:
    django.setup()
except RuntimeError:
    pass

from django.http import HttpRequest, JsonResponse
from api.services import GatewayError, NotFoundError, ValidationError
from api.views import _handle


def test_handle_maps_filenotfound_and_keyerror_to_404() -> None:
    @_handle
    def dummy_view(request: HttpRequest, service) -> JsonResponse:
        raise FileNotFoundError("Target file does not exist")

    req = HttpRequest()
    resp = dummy_view(req)
    assert resp.status_code == 404
    data = json.loads(resp.content)
    assert data["error"]["code"] == "not_found"


def test_handle_maps_unknown_entities_to_404_not_400() -> None:
    """Error dengan substring 'unknown' harus dipetakan ke 404, BUKAN 400 (perbaikan AEG-17)."""
    @_handle
    def dummy_view(request: HttpRequest, service) -> JsonResponse:
        raise RuntimeError("Unknown task id: task-999")

    req = HttpRequest()
    resp = dummy_view(req)
    assert resp.status_code == 404
    data = json.loads(resp.content)
    assert data["error"]["code"] == "not_found"
    assert "Unknown task id" in data["error"]["message"]


def test_handle_maps_validation_error_to_400() -> None:
    @_handle
    def dummy_view(request: HttpRequest, service) -> JsonResponse:
        raise ValueError("Invalid enum value for parameter")

    req = HttpRequest()
    resp = dummy_view(req)
    assert resp.status_code == 400
    data = json.loads(resp.content)
    assert data["error"]["code"] == "validation_error"


def test_handle_preserves_gateway_error() -> None:
    @_handle
    def dummy_view(request: HttpRequest, service) -> JsonResponse:
        raise NotFoundError("Project resource not found")

    req = HttpRequest()
    resp = dummy_view(req)
    assert resp.status_code == 404
    data = json.loads(resp.content)
    assert data["error"]["code"] == "not_found"
