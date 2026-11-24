"""Tests for speech configuration."""

from apex.core.config import ApexConfig, SpeechConfig


def test_speech_config_defaults():
    cfg = SpeechConfig()
    assert cfg.backend == "auto"
    assert cfg.model == "base"
    assert cfg.language == ""
    assert cfg.device == "auto"
    assert cfg.compute_type == "float16"


def test_apex_config_has_speech():
    cfg = ApexConfig()
    assert hasattr(cfg, "speech")
    assert isinstance(cfg.speech, SpeechConfig)
    assert cfg.speech.backend == "auto"


def test_apex_system_has_speech_backend():
    """ApexSystem has a speech_backend attribute."""
    from apex.system import ApexSystem

    assert "speech_backend" in ApexSystem.__dataclass_fields__

