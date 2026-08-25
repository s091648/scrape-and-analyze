"""
Unit tests for AsyncTranslateTagsUseCase — async sibling of
TranslateTagsUseCase (024-async-pipeline-refactor). Mirrors
test_translate_tags_use_case.py's coverage, adapted for the async/await
call path.
"""
import uuid
from unittest.mock import AsyncMock

import pytest

from src.modules.intelligence.application.use_cases.translate_tags import AsyncTranslateTagsUseCase
from src.modules.intelligence.domain.value_objects import TagTranslationPrompt, GroupTranslationPrompt


@pytest.fixture
def deps():
    llm_service = AsyncMock()
    repo = AsyncMock()
    tag_prompt = TagTranslationPrompt()
    group_prompt = GroupTranslationPrompt()
    return {
        "llm_service": llm_service,
        "tag_repo": repo,
        "tag_prompt": tag_prompt,
        "group_prompt": group_prompt,
    }


def _make_uc(deps):
    return AsyncTranslateTagsUseCase(
        llm_service=deps["llm_service"],
        tag_translation_repository=deps["tag_repo"],
        tag_prompt=deps["tag_prompt"],
        group_prompt=deps["group_prompt"],
    )


def _tag_id():
    return uuid.uuid4()


# ── translate_tags: success path ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_translate_tags_finds_tags_calls_llm_saves_positional_matches(deps):
    t1, t2, t3 = _tag_id(), _tag_id(), _tag_id()
    deps["tag_repo"].find_tags_without_translation.return_value = [
        {"tag_id": t1, "name": "AI"},
        {"tag_id": t2, "name": "IoT"},
        {"tag_id": t3, "name": "digital twin"},
    ]
    deps["llm_service"].translate.return_value = "人工智慧\n物聯網\n數位孿生"
    uc = _make_uc(deps)

    result = await uc.translate_tags("zh-TW", limit=50)

    assert result == {"total": 3, "success": 3, "failed": 0}
    deps["llm_service"].translate.assert_awaited_once()
    assert deps["tag_repo"].save_tag_translation.await_count == 3


@pytest.mark.asyncio
async def test_translate_tags_no_tags_returns_zero(deps):
    deps["tag_repo"].find_tags_without_translation.return_value = []
    uc = _make_uc(deps)

    result = await uc.translate_tags("zh-TW", limit=50)

    assert result == {"total": 0, "success": 0, "failed": 0}
    deps["llm_service"].translate.assert_not_awaited()


# ── translate_tags: unmatched lines (fewer LLM lines than tags) ──────────────

@pytest.mark.asyncio
async def test_translate_tags_counts_unmatched_as_failures(deps):
    t1, t2, t3 = _tag_id(), _tag_id(), _tag_id()
    deps["tag_repo"].find_tags_without_translation.return_value = [
        {"tag_id": t1, "name": "AI"},
        {"tag_id": t2, "name": "IoT"},
        {"tag_id": t3, "name": "digital twin"},
    ]
    deps["llm_service"].translate.return_value = "人工智慧\n物聯網"
    uc = _make_uc(deps)

    result = await uc.translate_tags("zh-TW", limit=50)

    assert result == {"total": 3, "success": 2, "failed": 1}


# ── translate_tags: LLM returns None ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_translate_tags_returns_all_failed_when_llm_returns_none(deps):
    t1 = _tag_id()
    deps["tag_repo"].find_tags_without_translation.return_value = [
        {"tag_id": t1, "name": "AI"},
    ]
    deps["llm_service"].translate.return_value = None
    uc = _make_uc(deps)

    result = await uc.translate_tags("zh-TW", limit=50)

    assert result == {"total": 1, "success": 0, "failed": 1}


# ── translate_tags: save exception counts as failure ─────────────────────────

@pytest.mark.asyncio
async def test_translate_tags_save_failure_counts_as_failed(deps):
    t1, t2 = _tag_id(), _tag_id()
    deps["tag_repo"].find_tags_without_translation.return_value = [
        {"tag_id": t1, "name": "AI"},
        {"tag_id": t2, "name": "IoT"},
    ]
    deps["llm_service"].translate.return_value = "人工智慧\n物聯網"
    deps["tag_repo"].save_tag_translation.side_effect = [
        None,
        Exception("db error"),
    ]
    uc = _make_uc(deps)

    result = await uc.translate_tags("zh-TW", limit=50)

    assert result == {"total": 2, "success": 1, "failed": 1}


# ── translate_groups: success path ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_translate_groups_finds_groups_calls_llm_saves_pipe_parsed(deps):
    g1, g2 = _tag_id(), _tag_id()
    deps["tag_repo"].find_groups_without_translation.return_value = [
        {"id": g1, "display_name": "Technology", "description": "Tech desc"},
        {"id": g2, "display_name": "Research", "description": None},
    ]
    deps["llm_service"].translate.return_value = "科技 | 科技描述\n研究"
    uc = _make_uc(deps)

    result = await uc.translate_groups("zh-TW", limit=50)

    assert result == {"total": 2, "success": 2, "failed": 0}
    save_calls = deps["tag_repo"].save_group_translation.call_args_list
    assert save_calls[0][1]["display_name"] == "科技"
    assert save_calls[0][1]["description"] == "科技描述"
    assert save_calls[1][1]["display_name"] == "研究"
    assert save_calls[1][1]["description"] is None


# ── translate_groups: group with no description ──────────────────────────────

@pytest.mark.asyncio
async def test_translate_groups_handles_no_description(deps):
    g1 = _tag_id()
    deps["tag_repo"].find_groups_without_translation.return_value = [
        {"id": g1, "display_name": "AI Tools", "description": None},
    ]
    deps["llm_service"].translate.return_value = "AI 工具"
    uc = _make_uc(deps)

    result = await uc.translate_groups("zh-TW", limit=50)

    assert result == {"total": 1, "success": 1, "failed": 0}
    save_call = deps["tag_repo"].save_group_translation.call_args
    assert save_call[1]["display_name"] == "AI 工具"
    assert save_call[1]["description"] is None


# ── translate_groups: unmatched lines ────────────────────────────────────────

@pytest.mark.asyncio
async def test_translate_groups_counts_unmatched_as_failures(deps):
    g1, g2, g3 = _tag_id(), _tag_id(), _tag_id()
    deps["tag_repo"].find_groups_without_translation.return_value = [
        {"id": g1, "display_name": "A", "description": "a"},
        {"id": g2, "display_name": "B", "description": "b"},
        {"id": g3, "display_name": "C", "description": "c"},
    ]
    deps["llm_service"].translate.return_value = "翻譯A | 描述a"
    uc = _make_uc(deps)

    result = await uc.translate_groups("zh-TW", limit=50)

    assert result == {"total": 3, "success": 1, "failed": 2}


# ── translate_groups: save exception counts as failure ────────────────────────

@pytest.mark.asyncio
async def test_translate_groups_save_failure_counts_as_failed(deps):
    g1, g2 = _tag_id(), _tag_id()
    deps["tag_repo"].find_groups_without_translation.return_value = [
        {"id": g1, "display_name": "A", "description": "a"},
        {"id": g2, "display_name": "B", "description": "b"},
    ]
    deps["llm_service"].translate.return_value = "翻譯A | 描述a\n翻譯B | 描述b"
    deps["tag_repo"].save_group_translation.side_effect = [
        None,
        Exception("db error"),
    ]
    uc = _make_uc(deps)

    result = await uc.translate_groups("zh-TW", limit=50)

    assert result == {"total": 2, "success": 1, "failed": 1}


# ── translate_groups: LLM returns None ───────────────────────────────────────

@pytest.mark.asyncio
async def test_translate_groups_returns_all_failed_when_llm_returns_none(deps):
    g1 = _tag_id()
    deps["tag_repo"].find_groups_without_translation.return_value = [
        {"id": g1, "display_name": "Tech", "description": None},
    ]
    deps["llm_service"].translate.return_value = None
    uc = _make_uc(deps)

    result = await uc.translate_groups("zh-TW", limit=50)

    assert result == {"total": 1, "success": 0, "failed": 1}


# ── translate_groups: no groups to translate ────────────────────────────────

@pytest.mark.asyncio
async def test_translate_groups_no_groups_returns_zero(deps):
    deps["tag_repo"].find_groups_without_translation.return_value = []
    uc = _make_uc(deps)

    result = await uc.translate_groups("zh-TW", limit=50)

    assert result == {"total": 0, "success": 0, "failed": 0}
    deps["llm_service"].translate.assert_not_awaited()
