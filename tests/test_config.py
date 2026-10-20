import pytest

from yoyakman.config import Settings


def test_defaults_keep_existing_summary_ux_without_credentials():
    settings = Settings.from_env({})
    assert settings.model == "gemini-2.5-flash"
    assert settings.max_messages == 300
    assert settings.summary_timeout == 120


def test_environment_overrides():
    settings = Settings.from_env(
        {
            "GEMINI_MODEL": "gemini-3.8-flash",
            "MAX_MESSAGES": "100",
            "SUMMARY_TIMEOUT": "25.5",
            "MAX_CONCURRENT_SUMMARIES": "3",
        }
    )
    assert settings.model == "gemini-3.8-flash"
    assert settings.max_messages == 100
    assert settings.summary_timeout == 25.5
    assert settings.max_concurrent_summaries == 3


@pytest.mark.parametrize(
    "env",
    [
        {"MAX_MESSAGES": "301"},
        {"MAX_MESSAGES": "0"},
        {"MAX_HISTORY_MESSAGES": "200"},
        {"SUMMARY_TIMEOUT": "nan"},
        {"COLLECTION_TIMEOUT": "inf"},
        {"API_MAX_ATTEMPTS": "6"},
        {"GEMINI_MODEL": " "},
        {"MAX_RESPONSE_MESSAGES": "0"},
        {"MAX_RESPONSE_MESSAGES": "6"},
        {"MAX_CONCURRENT_SUMMARIES": "0"},
    ],
)
def test_invalid_config_is_rejected(env):
    with pytest.raises(ValueError):
        Settings.from_env(env)


def test_invalid_env_value_is_not_leaked_in_error():
    with pytest.raises(ValueError) as error:
        Settings.from_env({"MAX_MESSAGES": "secret-placeholder"})
    assert "secret-placeholder" not in str(error.value)
