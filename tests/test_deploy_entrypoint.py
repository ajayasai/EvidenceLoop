"""Deployment configuration checks do not start containers or contact hosts."""
from pathlib import Path
import pytest

from scripts.deploy_entrypoint import deployment_settings, postgres_arguments, runtime_environment


def test_render_origin_and_port_are_used_without_loading_external_secrets():
    assert deployment_settings({"RENDER_EXTERNAL_URL":"https://example.onrender.com/","PORT":"10000"}) == ("https://example.onrender.com", 10000)
    assert deployment_settings({"APP_ORIGIN":"https://demo.example.org"}) == ("https://demo.example.org", 7860)
    environment = runtime_environment({"EVIDENCELOOP_LIVE_ENABLED":"true","EVIDENCELOOP_MODEL_API_KEY":"fictional-key",
        "REVIEWER_TOKEN":"fictional-review","EDITOR_TOKEN":"fictional-editor", "DATABASE_ADMIN_URL":"fictional-admin",
        "EVIDENCELOOP_REVIEW_ACCESS_FILE":"private.json","PORT":"10000"}, "fictional-runtime-database", "https://demo.example.org")
    assert environment["EVIDENCELOOP_LIVE_ENABLED"] == "false"
    assert environment["EVIDENCELOOP_ALIGNMENT_ENABLED"] == "false"
    assert environment["EVIDENCELOOP_MODEL_API_KEY"] == environment["EVIDENCELOOP_REVIEW_ACCESS_FILE"] == ""
    assert environment["REVIEWER_TOKEN"] == environment["EDITOR_TOKEN"] == ""
    assert "DATABASE_ADMIN_URL" not in environment
    assert environment["DATABASE_URL"] == "fictional-runtime-database"
    assert environment["EVIDENCELOOP_PUBLIC_DEMO"] == "true"


@pytest.mark.parametrize("values", [{}, {"APP_ORIGIN":"http://example.org"}, {"APP_ORIGIN":"https://example.org/path"},
    {"APP_ORIGIN":"https://user:password@example.org"}, {"APP_ORIGIN":"https://example.org","PORT":"80"},
    {"APP_ORIGIN":"https://example.org","PORT":"65536"}, {"APP_ORIGIN":"https://example.org","PORT":"bad"}])
def test_invalid_deployment_configuration_fails_before_startup(values):
    with pytest.raises(ValueError):
        deployment_settings(values)


def test_database_binds_only_loopback_with_bounded_memory():
    args = postgres_arguments(Path("/bin/postgres"), Path("/tmp/fresh-demo/postgres"), 15432)
    assert "listen_addresses=127.0.0.1" in args and "unix_socket_directories=" in args
    assert "shared_buffers=16MB" in args and "max_connections=20" in args
    assert "max_worker_processes=0" in args
    assert "log_statement=none" in args and "log_min_error_statement=panic" in args
