import pytest

from tech_ai.config.azure import AzureSettings
from tech_ai.errors import ConfigurationError


def test_azure_is_disabled_with_conservative_defaults() -> None:
    settings = AzureSettings.from_environment({})
    assert not settings.speech_enabled
    assert not settings.language_enabled
    assert not settings.document_enabled
    assert settings.speech_region == "brazilsouth"
    assert settings.max_audio_seconds == 120
    assert settings.max_document_pages == 10
    assert settings.max_text_records_per_analysis == 20
    assert settings.max_concurrent_requests == 1


def test_enabled_services_require_private_credentials() -> None:
    with pytest.raises(ConfigurationError, match="SPEECH_KEY"):
        AzureSettings.from_environment({"TECH_AI_AZURE_SPEECH_ENABLED": "true"})
    with pytest.raises(ConfigurationError, match="LANGUAGE_KEY"):
        AzureSettings.from_environment({"TECH_AI_AZURE_LANGUAGE_ENABLED": "true"})
    with pytest.raises(ConfigurationError, match="DOCUMENT_KEY"):
        AzureSettings.from_environment({"TECH_AI_AZURE_DOCUMENT_ENABLED": "true"})


def test_enabled_services_accept_https_endpoints_and_hide_keys() -> None:
    settings = AzureSettings.from_environment(
        {
            "TECH_AI_AZURE_SPEECH_ENABLED": "true",
            "TECH_AI_AZURE_SPEECH_KEY": "speech-secret",
            "TECH_AI_AZURE_SPEECH_REGION": "BrazilSouth",
            "TECH_AI_AZURE_LANGUAGE_ENABLED": "true",
            "TECH_AI_AZURE_LANGUAGE_KEY": "language-secret",
            "TECH_AI_AZURE_LANGUAGE_ENDPOINT": "https://language.example.azure.com/",
            "TECH_AI_AZURE_DOCUMENT_ENABLED": "true",
            "TECH_AI_AZURE_DOCUMENT_KEY": "document-secret",
            "TECH_AI_AZURE_DOCUMENT_ENDPOINT": "https://document.example.azure.com/",
        }
    )
    rendered = repr(settings)
    assert settings.speech_region == "brazilsouth"
    assert "speech-secret" not in rendered
    assert "language-secret" not in rendered
    assert "document-secret" not in rendered


@pytest.mark.parametrize(
    "environment,match",
    [
        ({"TECH_AI_AZURE_SPEECH_ENABLED": "maybe"}, "true ou false"),
        (
            {
                "TECH_AI_AZURE_LANGUAGE_ENABLED": "true",
                "TECH_AI_AZURE_LANGUAGE_KEY": "secret",
                "TECH_AI_AZURE_LANGUAGE_ENDPOINT": "http://insecure.example.com",
            },
            "URL HTTPS",
        ),
        (
            {"TECH_AI_AZURE_SPEECH_REGION": "Brazil South"},
            "REGION inválida",
        ),
        (
            {"TECH_AI_AZURE_MAX_AUDIO_SECONDS": "121"},
            "não pode exceder 120",
        ),
        (
            {"TECH_AI_AZURE_MAX_CONCURRENT_REQUESTS": "5"},
            "não pode exceder 4",
        ),
        (
            {"TECH_AI_AZURE_MAX_DOCUMENT_PAGES": "0"},
            "maior que zero",
        ),
    ],
)
def test_azure_rejects_unsafe_or_excessive_configuration(
    environment: dict[str, str], match: str
) -> None:
    with pytest.raises(ConfigurationError, match=match):
        AzureSettings.from_environment(environment)
