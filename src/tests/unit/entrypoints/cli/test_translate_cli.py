"""
Unit tests for the translate CLI entry point — covers language validation,
pipeline invocation, and default limit behavior.
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.modules.intelligence.domain.value_objects import LANGUAGE_NAMES

SUPPORTED_LANGUAGES = LANGUAGE_NAMES


# ── Language validation ─────────────────────────────────────────────────────

def test_unsupported_language_exits_with_error():
    with patch("sys.argv", ["translate", "--language", "xx-YY"]):
        with patch("src.entrypoints.cli.translate.validate_config"):
            with patch("src.entrypoints.cli.translate.configure_logging"):
                with patch("src.entrypoints.cli.translate.init_default_client"):
                    with pytest.raises(SystemExit) as exc_info:
                        from src.entrypoints.cli.translate import main
                        main()
                    assert exc_info.value.code == 1


# ── Fetches untranslated analyses and calls use case ────────────────────────

@patch("src.entrypoints.cli.translate.build_translation_pipeline")
@patch("src.entrypoints.cli.translate.init_default_client")
@patch("src.entrypoints.cli.translate.configure_logging")
@patch("src.entrypoints.cli.translate.validate_config")
def test_fetches_untranslated_and_calls_execute(mock_validate, mock_logging, mock_http, mock_pipeline):
    aid = uuid.uuid4()
    article_id = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.success = True

    mock_translate_uc = MagicMock()
    mock_translate_uc.execute.return_value = mock_result

    mock_repo = MagicMock()
    mock_repo.find_analyses_without_translation.return_value = [
        {"analysis_id": aid, "article_id": article_id, "summary": "s", "pain_points": "p", "insights": "i", "innovations": "n"},
    ]

    mock_tag_uc = MagicMock()
    mock_tag_uc.translate_tags.return_value = {"total": 0, "success": 0, "failed": 0}
    mock_tag_uc.translate_groups.return_value = {"total": 0, "success": 0, "failed": 0}

    mock_pipeline.return_value = {
        "use_case": mock_translate_uc,
        "analyses_translation_repository": mock_repo,
        "tag_use_case": mock_tag_uc,
        "tag_translation_repository": MagicMock(),
    }

    with patch("sys.argv", ["translate", "--language", "zh-TW", "--limit", "5"]):
        from src.entrypoints.cli.translate import main
        main()

    mock_repo.find_analyses_without_translation.assert_called_once_with("zh-TW", 5)
    mock_translate_uc.execute.assert_called_once_with(
        analysis_id=aid, summary="s", pain_points="p",
        insights="i", innovations="n", target_language="zh-TW",
    )


# ── Calls translate_tags and translate_groups after article loop ─────────────

@patch("src.entrypoints.cli.translate.build_translation_pipeline")
@patch("src.entrypoints.cli.translate.init_default_client")
@patch("src.entrypoints.cli.translate.configure_logging")
@patch("src.entrypoints.cli.translate.validate_config")
def test_calls_tag_and_group_translation(mock_validate, mock_logging, mock_http, mock_pipeline):
    mock_translate_uc = MagicMock()
    mock_result = MagicMock()
    mock_result.success = True
    mock_translate_uc.execute.return_value = mock_result

    mock_repo = MagicMock()
    mock_repo.find_analyses_without_translation.return_value = []

    mock_tag_uc = MagicMock()
    mock_tag_uc.translate_tags.return_value = {"total": 0, "success": 0, "failed": 0}
    mock_tag_uc.translate_groups.return_value = {"total": 0, "success": 0, "failed": 0}

    mock_pipeline.return_value = {
        "use_case": mock_translate_uc,
        "analyses_translation_repository": mock_repo,
        "tag_use_case": mock_tag_uc,
        "tag_translation_repository": MagicMock(),
    }

    with patch("sys.argv", ["translate", "--language", "ja", "--limit", "10"]):
        from src.entrypoints.cli.translate import main
        main()

    mock_tag_uc.translate_tags.assert_called_once_with("ja", 10)
    mock_tag_uc.translate_groups.assert_called_once_with("ja", 10)


# ── Default limit is 10 ─────────────────────────────────────────────────────

@patch("src.entrypoints.cli.translate.build_translation_pipeline")
@patch("src.entrypoints.cli.translate.init_default_client")
@patch("src.entrysteps.cli.translate.configure_logging")
@patch("src.entrypoints.cli.translate.validate_config")
def test_default_limit_is_10(mock_validate, mock_logging, mock_http, mock_pipeline):
    mock_repo = MagicMock()
    mock_repo.find_analyses_without_translation.return_value = []

    mock_tag_uc = MagicMock()
    mock_tag_uc.translate_tags.return_value = {"total": 0, "success": 0, "failed": 0}
    mock_tag_uc.translate_groups.return_value = {"total": 0, "success": 0, "failed": 0}

    mock_pipeline.return_value = {
        "use_case": MagicMock(),
        "analyses_translation_repository": mock_repo,
        "tag_use_case": mock_tag_uc,
        "tag_translation_repository": MagicMock(),
    }

    with patch("sys.argv", ["translate", "--language", "zh-TW"]):
        from src.entrypoints.cli.translate import main
        main()

    mock_repo.find_analyses_without_translation.assert_called_once_with("zh-TW", 10)
