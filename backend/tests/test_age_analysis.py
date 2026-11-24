import json

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings
from app.schemas.analysis import AgeAnalysisResult, RestrictionType
from app.services.age_analysis import (
    AnalysisConfigurationError,
    AnalysisProviderError,
    OpenAICompatibleAgeAnalyzer,
)


def valid_analysis(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "has_age_restriction": True,
        "restriction_type": "EXPLICIT",
        "min_age": None,
        "max_age": 28,
        "extracted_evidence": "Usia maksimal 28 tahun",
        "ai_reasoning": "Batas maksimal usia disebutkan secara eksplisit.",
        "confidence_score": 0.98,
    }
    result.update(overrides)
    return result


def test_analysis_schema_rejects_inconsistent_restriction_and_age_range() -> None:
    with pytest.raises(ValidationError):
        AgeAnalysisResult.model_validate(
            valid_analysis(has_age_restriction=False, max_age=20)
        )

    with pytest.raises(ValidationError):
        AgeAnalysisResult.model_validate(valid_analysis(min_age=35, max_age=20))


def test_analysis_schema_requires_evidence_for_restrictions() -> None:
    with pytest.raises(ValidationError):
        AgeAnalysisResult.model_validate(valid_analysis(extracted_evidence="  "))


def test_analysis_schema_accepts_neutral_result() -> None:
    result = AgeAnalysisResult.model_validate(
        valid_analysis(
            has_age_restriction=False,
            restriction_type=RestrictionType.NONE,
            max_age=None,
            extracted_evidence=None,
            ai_reasoning="Tidak ditemukan batasan usia pada teks.",
        )
    )

    assert result.restriction_type is RestrictionType.NONE


@pytest.mark.asyncio
async def test_analyzer_requests_and_validates_structured_output() -> None:
    settings = Settings(
        llm_base_url="https://llm.example/v1",
        llm_api_key=SecretStr("test-key"),
        llm_model="test-model",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(valid_analysis())}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        analyzer = OpenAICompatibleAgeAnalyzer(settings, client)
        result = await analyzer.analyze("Usia maksimal 28 tahun")

    assert result.restriction_type is RestrictionType.EXPLICIT
    assert result.max_age == 28


@pytest.mark.asyncio
async def test_analyzer_surfaces_provider_status_without_response_body() -> None:
    settings = Settings(
        llm_base_url="https://llm.example/v1",
        llm_api_key=SecretStr("test-key"),
        llm_model="test-model",
    )

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="sensitive provider response")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        analyzer = OpenAICompatibleAgeAnalyzer(settings, client)
        with pytest.raises(AnalysisProviderError, match="HTTP 401") as error:
            await analyzer.analyze("Description")

    assert "sensitive provider response" not in str(error.value)
    assert "test-key" not in str(error.value)


@pytest.mark.asyncio
async def test_analyzer_rejects_missing_credentials() -> None:
    analyzer = OpenAICompatibleAgeAnalyzer(
        Settings(llm_api_key=SecretStr(""), llm_model="test-model")
    )

    with pytest.raises(AnalysisConfigurationError, match="LLM_API_KEY"):
        await analyzer.analyze("Description")


@pytest.mark.asyncio
async def test_analyzer_rejects_invalid_structured_output() -> None:
    settings = Settings(
        llm_base_url="https://llm.example/v1",
        llm_api_key=SecretStr("test-key"),
        llm_model="test-model",
    )

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"restriction_type":"INVALID"}'}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        analyzer = OpenAICompatibleAgeAnalyzer(settings, client)
        with pytest.raises(AnalysisProviderError, match="invalid structured analysis"):
            await analyzer.analyze("Description")
