"""Automated Token & Structure Checks for UI Refactor."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "web" / "frontend" / "src"

def test_neutral_green_tokens():
    styles_css = (FRONTEND / "styles.css").read_text(encoding="utf-8")
    assert "--accent:     #2d7d4e;" in styles_css or "--accent: #2d7d4e;" in styles_css or "--accent:   #2d7d4e;" in styles_css, "Dark theme --accent must be #2d7d4e"
    assert "--accent-dim: #23653f;" in styles_css, "Dark theme --accent-dim must be #23653f"
    assert "--accent-muted:#5ebd87;" in styles_css, "Dark theme --accent-muted must be #5ebd87"
    
    # Check no lingering old teal rgba(26, 122, 110
    lingering = []
    for f in FRONTEND.rglob("*"):
        if f.is_file() and f.suffix in [".vue", ".css", ".js", ".ts"]:
            text = f.read_text(encoding="utf-8")
            if re.search(r"rgba\(\s*26\s*,\s*122\s*,\s*110", text):
                lingering.append(f.name)
            if re.search(r"#1a7a6e", text):
                lingering.append(f.name)
            if re.search(r"#1a6b61", text):
                lingering.append(f.name)
    assert not lingering, f"Lingering teal tokens in: {lingering}"

def test_actions_column_header():
    app_vue = (FRONTEND / "App.vue").read_text(encoding="utf-8")
    assert re.search(r'<th\s+[^>]*class="[^"]*th-actions[^"]*"[^>]*>\s*Actions\s*</th>', app_vue), "App.vue must contain Actions column header with th-actions"
    
    styles_css = (FRONTEND / "styles.css").read_text(encoding="utf-8")
    assert ".th-actions" in styles_css, "styles.css must define .th-actions"

def test_task_history_row_actions():
    app_vue = (FRONTEND / "App.vue").read_text(encoding="utf-8")
    assert "hist-report-btn" in app_vue, "App.vue must use .hist-report-btn"
    assert not re.search(r'<button class="report-btn"[^>]*>Report</button>', app_vue), "App.vue should not contain text-only Report button in hist-table"
    
    styles_css = (FRONTEND / "styles.css").read_text(encoding="utf-8")
    assert ".hist-report-btn" in styles_css, "styles.css must define .hist-report-btn"

def test_queue_panel_row_actions_and_badges():
    queue_vue = (FRONTEND / "components" / "QueuePanel.vue").read_text(encoding="utf-8")
    assert "q-actions" in queue_vue, "QueuePanel.vue must contain .q-actions"
    assert "q-view-btn" in queue_vue, "QueuePanel.vue must contain .q-view-btn"
    assert "q-del-btn" in queue_vue, "QueuePanel.vue must contain .q-del-btn"
    assert '<span class="q-badge">{{ tasks.length }}</span>' in queue_vue, "QueuePanel.vue must not have raw brackets around q-badge"

def test_unified_badges_and_slider_toggle():
    styles_css = (FRONTEND / "styles.css").read_text(encoding="utf-8")
    assert ".aether-badge" in styles_css, "styles.css must define .aether-badge"
    assert ".slider-toggle" in styles_css, "styles.css must define .slider-toggle"
    assert ".slider-track" in styles_css, "styles.css must define .slider-track"
    assert ".slider-thumb" in styles_css, "styles.css must define .slider-thumb"
    
    gs_vue = (FRONTEND / "components" / "GlobalSettingsPanel.vue").read_text(encoding="utf-8")
    assert "slider-toggle" in gs_vue, "GlobalSettingsPanel.vue must use slider-toggle"
    assert "#2d7d4e" in gs_vue, "GlobalSettingsPanel.vue must use #2d7d4e for active switch"

if __name__ == "__main__":
    test_neutral_green_tokens()
    test_actions_column_header()
    test_task_history_row_actions()
    test_queue_panel_row_actions_and_badges()
    test_unified_badges_and_slider_toggle()
    print("ALL UI REFACTOR AUTOMATED CHECKS PASSED!")
