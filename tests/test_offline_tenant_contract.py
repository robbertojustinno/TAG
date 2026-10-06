from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFLINE = (ROOT / "admin" / "offline-store.js").read_text(encoding="utf-8")
APP = (ROOT / "admin" / "app.js").read_text(encoding="utf-8")\nINTEGRATION = (ROOT / "admin" / "offline-integration.js").read_text(encoding="utf-8")


def test_offline_database_is_company_scoped():
    assert "tagcheck_offline_company_" in OFFLINE
    assert "requireCompanyId(companyId)" in OFFLINE
    assert "Number(row.company_id) === id" in OFFLINE


def test_offline_queue_carries_company_and_user_metadata():
    assert "company_id: id" in OFFLINE
    assert "user_id:" in OFFLINE
    assert "pending_sync" in OFFLINE


def test_offline_context_respects_session_expiration():
    assert "Date.now() >= value.expires_at" in OFFLINE
    assert "tokenExpiryMs" in OFFLINE


def test_frontend_keeps_company_identity_for_offline_scope():
    assert "companyId:" in APP
    assert "identity.company_id" in APP


def test_sync_refuses_cross_company_session():
    assert "claimCompany" in INTEGRATION
    assert "Number(claimCompany) !== Number(s.companyId)" in INTEGRATION
    assert "Number(row.company_id) !== Number(s.companyId)" in INTEGRATION


def test_offline_capture_requires_current_company_context():
    assert "activeContext()" in INTEGRATION
    assert "Number(context.company_id) !== Number(s.companyId)" in INTEGRATION
