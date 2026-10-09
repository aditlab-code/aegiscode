"""Unit test untuk endpoint GET /api/skills/catalog.

Memverifikasi:
1. Endpoint merespons 200 OK dengan format {"status": "ok", "skills": [...]}.
2. Seluruh 9 skills resmi Addy Osmani terdaftar lengkap.
3. Struktur tiap entri memiliki command ringkas dan placeholder template.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from django.test import Client

REPO_ROOT = Path(__file__).resolve().parent.parent
DJANGO_APP_DIR = REPO_ROOT / "apps" / "django_app"
SRC_DIR = REPO_ROOT / "src"

for p in (str(DJANGO_APP_DIR), str(SRC_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()


def test_skills_catalog_endpoint_success():
    client = Client()
    response = client.get("/api/skills/catalog")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "skills" in data
    assert isinstance(data["skills"], list)
    assert len(data["skills"]) >= 9

    # Verifikasi 9 skills resmi ada di dalam response
    skill_ids = [s["skill_id"] for s in data["skills"]]
    expected = [
        "spec-driven-development",
        "planning-and-task-breakdown",
        "incremental-implementation",
        "test-driven-development",
        "interview-me",
        "code-review-and-quality",
        "constraint-driven-development",
        "code-simplification",
        "shipping-and-launch",
    ]
    for exp in expected:
        assert exp in skill_ids, f"Skill {exp} tidak ditemukan di katalog API"

    # Verifikasi struktur objek
    spec_item = next(s for s in data["skills"] if s["skill_id"] == "spec-driven-development")
    assert spec_item["command"] == "/spec"
    assert spec_item["id"] == "spec"
    assert "/spec [Jelaskan spesifikasi" in spec_item["template"]
    assert "Spec-Driven Development" in spec_item["name"]


def test_skills_catalog_with_workspace_param():
    client = Client()
    response = client.get(f"/api/skills/catalog?workspace={REPO_ROOT}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert len(data["skills"]) >= 9
