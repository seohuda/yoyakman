"""bot.py 순수 로직 회귀 테스트. Discord/Gemini 네트워크는 타지 않는다."""

import bot


def test_generation_config_does_not_cap_output_tokens():
    """gemini-2.5는 사고 토큰이 출력 상한을 잠식한다. 4096으로 깎지 말고 모델 기본값을 쓴다."""
    cfg = bot.gemini_model._generation_config
    assert "max_output_tokens" not in cfg
