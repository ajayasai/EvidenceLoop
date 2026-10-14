"""Public replay hosting never inherits local inference or reviewer authority."""
import pytest
from fastapi.testclient import TestClient

from services.api.app.main import create_app
from tests.test_api import make_receipt, save_receipt


class ConfiguredCompiler:
    available = alignment_available = True
    extraction_scope = "remote"

    async def extract(self, *args):
        raise AssertionError("Public replay must never call a model")


@pytest.fixture
def public_app(monkeypatch, isolated_database):
    monkeypatch.setenv("EVIDENCELOOP_PUBLIC_DEMO", "true")
    monkeypatch.setenv("APP_ORIGIN", "https://demo.example.org")
    monkeypatch.setenv("REVIEWER_TOKEN", "fictional-local-review-credential")
    monkeypatch.setenv("EDITOR_TOKEN", "fictional-local-editor-credential")
    monkeypatch.setenv("EVIDENCELOOP_REVIEW_ACCESS_FILE", "/never/read/private/review.json")
    return create_app(isolated_database.url, compiler=ConfiguredCompiler())


def session_client(app):
    client = TestClient(app, base_url="https://demo.example.org")
    response = client.get("/api/session")
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    client.headers["Origin"] = "https://demo.example.org"
    return client, response


def test_public_demo_cookie_and_host_boundary(public_app):
    with TestClient(public_app, base_url="http://demo.example.org") as client:
        response = client.get("/api/session")
        for cookie in response.headers.get_list("set-cookie"):
            assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie
        data = response.json()
        assert data["public_demo"] and data["storage_resets_on_restart"] and data["synthetic"]
        assert not data["live_available"] and not data["extraction_available"] and not data["alignment_available"]
        assert data["preferred_mode"] == "replay" and data["extraction_scope"] is None
        assert client.get("/api/health", headers={"Host":"untrusted.example.org"}).status_code == 400
        assert client.get("/api/health", headers={"Host":"127.0.0.1"}).status_code == 200


def test_public_demo_denies_arbitrary_inputs_models_review_and_cross_origin(public_app):
    with TestClient(public_app):
        client, _ = session_client(public_app)
        example = client.get("/api/examples").json()[0]
        for mode, text in (("live", example["text"]), ("manual", example["text"]), ("replay", "Arbitrary private wording")):
            assert client.post("/api/claims", json={"mode":mode,"text":text}).status_code == 422
        assert client.post("/api/claims", json={"text":example["text"]}, headers={"Origin":"http://localhost:8765"}).status_code == 403
        for path, payload in (("login", {"token":"fictional-local-review-credential"}),
                              ("editor-login", {"token":"fictional-local-editor-credential"}),
                              ("sources/demo/decision", {"expected_revision":1,"decision":"withdraw","reason":"Demo withdrawal"})):
            assert client.post("/api/review/"+path, json=payload).status_code == 403
        assert client.get("/api/review/sources").status_code == 403
        assert client.get("/api/review/queue").status_code == 403
        client.close()


def test_public_replay_retains_save_consent_private_ownership_and_checkin(public_app):
    with TestClient(public_app):
        first, _ = session_client(public_app)
        second, _ = session_client(public_app)
        receipt = make_receipt(first)
        assert receipt["receipt"]["comparison_basis"] == "authored_replay"
        step, _, _ = save_receipt(first, receipt)
        assert second.get("/api/next-steps").json()["items"] == []
        assert second.get("/api/receipts/"+receipt["receipt_id"]).status_code == 404
        assert second.post(f"/api/next-steps/{step['id']}/check-ins", json={"expected_version":1,"state":"deferred","consent":True}).status_code == 404
        denied = first.post(f"/api/next-steps/{step['id']}/check-ins", json={"expected_version":1,"state":"deferred","consent":False})
        assert denied.status_code == 422
        done = first.post(f"/api/next-steps/{step['id']}/check-ins", json={"expected_version":1,"state":"deferred","consent":True})
        assert done.status_code == 200 and done.json()["saved"] is True
        assert first.delete("/api/account/data").status_code == 200
        first.close()
        second.close()


@pytest.mark.parametrize("origin", ["", "http://demo.example.org", "https://user:secret@demo.example.org", "https://demo.example.org/path", "https://demo.example.org?key=private", "https://*.example.org"])
def test_public_demo_rejects_unsafe_origin(monkeypatch, origin):
    monkeypatch.setenv("EVIDENCELOOP_PUBLIC_DEMO", "true")
    monkeypatch.setenv("APP_ORIGIN", origin)
    with pytest.raises(ValueError):
        create_app("unused")


def test_demo_media_supports_ranges_without_serving_parent_files(monkeypatch, isolated_database, tmp_path):
    from services.api.app import main
    dist = tmp_path / "apps/web/dist"
    media = dist / "demo"
    media.mkdir(parents=True)
    (dist / "demo-video.html").write_text("<title>Fictional replay video</title>", encoding="utf-8")
    (media / "example.mp4").write_bytes(b"fictional-video-range-check")
    (media / "example.vtt").write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nFictional replay\n", encoding="utf-8")
    (tmp_path / "private.txt").write_text("unavailable private sentinel", encoding="utf-8")
    monkeypatch.setattr(main, "ROOT", tmp_path)
    with TestClient(create_app(isolated_database.url)) as client:
        page = client.get("/demo-video.html")
        assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")
        video = client.get("/demo/example.mp4", headers={"Range":"bytes=0-3"})
        assert video.status_code == 206 and video.content == b"fict"
        assert video.headers["content-range"] == "bytes 0-3/27"
        assert client.get("/demo/example.vtt").headers["content-type"].startswith("text/vtt")
        assert client.get("/demo/%2e%2e/%2e%2e/%2e%2e/private.txt").status_code == 404
