import io
import os
import sys
import pytest
from werkzeug.datastructures import FileStorage

# Ensure workspace root is on sys.path
WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

import app as argus_app


@pytest.fixture(scope="module")
def client():
    argus_app.app.config["TESTING"] = True
    argus_app.app.config["WTF_CSRF_ENABLED"] = True
    with argus_app.app.test_client() as c:
        yield c


def test_security_headers_on_login(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    assert "base-uri 'self'" in csp
    assert "no-store" in resp.headers.get("Cache-Control", "")


def test_session_cookie_flags():
    cfg = argus_app.app.config
    assert cfg.get("SESSION_COOKIE_HTTPONLY") is True
    assert cfg.get("SESSION_COOKIE_SAMESITE") == "Lax"
    assert cfg.get("SESSION_COOKIE_SECURE") is True
    assert len(argus_app.app.secret_key) >= 32


@pytest.mark.parametrize("path", [
    "/dashboard",
    "/manage-companies",
    "/manage-branches",
    "/field-worker",
])
def test_unauthenticated_pages_redirect(client, path):
    resp = client.get(path, follow_redirects=False)
    assert resp.status_code in (302, 401, 403), f"{path} returned {resp.status_code}"


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/employees"),
    ("GET", "/api/companies"),
    ("GET", "/api/branches"),
    ("GET", "/api/field-worker/overview"),
    ("GET", "/api/admin/leave-permission/requests"),
    ("GET", "/api/employee/leave-balance"),
    ("GET", "/api/payslip/export/pdf"),
    ("POST", "/api/mobile/employee/leave-requests/apply"),
    ("POST", "/api/mobile/employee/credentials"),
])
def test_unauthenticated_apis_blocked(client, method, path):
    resp = client.open(path, method=method)
    assert resp.status_code in (400, 401, 403), f"{method} {path} returned {resp.status_code}"


def test_rbac_company_admin_blocked_from_super_admin(client):
    with client.session_transaction() as sess:
        sess.clear()
        sess["admin_logged_in"] = True
        sess["role"] = "company_admin"
        sess["company_id"] = "TEST_COMP"
    resp = client.get("/api/companies")
    assert resp.status_code == 403
    resp_page = client.get("/manage-companies", follow_redirects=False)
    assert resp_page.status_code in (302, 403)


def test_rbac_employee_blocked_from_admin_and_field_register(client):
    with client.session_transaction() as sess:
        sess.clear()
        sess["employee_logged_in"] = True
        sess["role"] = "employee"
        sess["employee_id"] = "EMP_TEST"
        sess["company_id"] = "TEST_COMP"
    assert client.get("/api/employees").status_code in (401, 403)
    assert client.get("/api/branches").status_code in (401, 403)


def test_csrf_enforced_on_web_post(client):
    with client.session_transaction() as sess:
        sess.clear()
        sess["admin_logged_in"] = True
        sess["role"] = "company_admin"
        sess["company_id"] = "TEST_COMP"
    resp = client.post("/api/branches", json={"branch_name": "EvilBranch"})
    assert resp.status_code == 400


@pytest.mark.parametrize("path", [
    "/uploads/../../app.py",
    "/uploads/%2e%2e/%2e%2e/app.py",
    "/uploads/leaves/../../.env",
    "/uploads/employee_documents/../../app.py",
])
def test_path_traversal_blocked(client, path):
    with client.session_transaction() as sess:
        sess.clear()
        sess["admin_logged_in"] = True
        sess["role"] = "super_admin"
    resp = client.get(path)
    assert resp.status_code in (400, 403, 404), f"Traversal {path} returned {resp.status_code}"


def test_safe_save_file_rejects_malicious_uploads(tmp_path):
    for bad_name, content in [
        ("shell.php", b"<?php echo 1; ?>"),
        ("xss.svg", b"<svg onload=alert(1)>"),
        ("page.html", b"<script>alert(1)</script>"),
    ]:
        fs = FileStorage(stream=io.BytesIO(content), filename=bad_name)
        with pytest.raises(ValueError):
            argus_app.safe_save_file(fs, str(tmp_path), {"png", "jpg", "pdf"})

    spoofed = FileStorage(stream=io.BytesIO(b"<?php system('id'); ?>"), filename="avatar.png")
    with pytest.raises(ValueError, match="PNG signature"):
        argus_app.safe_save_file(spoofed, str(tmp_path), {"png", "jpg"})

    valid_png = FileStorage(stream=io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32), filename="valid.png")
    saved_name, orig_name, saved_path = argus_app.safe_save_file(valid_png, str(tmp_path), {"png", "jpg"})
    assert saved_name.endswith(".png")
    assert orig_name == "valid.png"
    assert os.path.isfile(saved_path)


def test_login_rate_limiting(client):
    with client.session_transaction() as sess:
        sess.clear()
    statuses = []
    argus_app.app.config["WTF_CSRF_ENABLED"] = False
    try:
        for _ in range(12):
            r = client.post("/login", data={"username": "nonexistent", "password": "wrong"})
            statuses.append(r.status_code)
    finally:
        argus_app.app.config["WTF_CSRF_ENABLED"] = True
    assert 429 in statuses, f"Expected 429 rate limit, got {statuses}"
