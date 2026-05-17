from opsincident_collector.config.settings import AppSettings
from opsincident_collector.core.models import NormalizedDocumentEnvelope
from opsincident_collector.core.protocol import CORE_API_VERSION, SCHEMA_VERSION, collector_version


def test_token_env_is_resolved(monkeypatch) -> None:
    monkeypatch.setenv("CUSTOM_INCIDENTOPS_TOKEN", "token-value")
    settings = AppSettings()
    settings.api.token_env = "CUSTOM_INCIDENTOPS_TOKEN"

    assert settings.api.resolve_token() == "token-value"


def test_protocol_constants_are_available() -> None:
    assert collector_version()
    assert SCHEMA_VERSION == "incidentops.normalized_document.v1"
    assert CORE_API_VERSION == "v1"
    assert NormalizedDocumentEnvelope.model_fields["schema_version"].default == SCHEMA_VERSION
