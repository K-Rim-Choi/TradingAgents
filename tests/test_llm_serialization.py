"""Parallel analysts share a model whose tracing metadata is cached lazily."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from langchain_core.load import dumpd
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel

from tradingagents.llm_clients.openai_client import (
    ChatGPTPlanChatOpenAI,
    DeepSeekChatOpenAI,
    LocalCompatibleChatOpenAI,
    MinimaxChatOpenAI,
    NormalizedChatOpenAI,
)


@pytest.mark.unit
@pytest.mark.parametrize("client_class", [
    NormalizedChatOpenAI, ChatGPTPlanChatOpenAI, DeepSeekChatOpenAI,
    LocalCompatibleChatOpenAI, MinimaxChatOpenAI,
])
def test_parallel_tool_bound_calls_can_serialize_the_same_model(monkeypatch, client_class):
    llm = client_class(model="gpt-4o-mini", api_key="test-key", streaming=False)
    started, release = Event(), Event()

    class PausingKey(str):
        def startswith(self, *args, **kwargs):
            # Pause the first iterator while the other caller computes and
            # stores _serialized in the shared model's __dict__.
            if not started.is_set():
                started.set()
                assert release.wait(5), "other caller did not finish serialization"
            return super().startswith(*args, **kwargs)

    value = llm.__dict__.pop("model_name")
    llm.__dict__[PausingKey("model_name")] = value

    def generate(*args, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="report"))])

    monkeypatch.setattr(NormalizedChatOpenAI, "_generate", generate)
    tool = {"type": "function", "function": {"name": "fundamentals", "parameters": {
        "type": "object", "properties": {},
    }}}
    bound = llm.bind_tools([tool])
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(bound.invoke, "Analyze fundamentals")
        try:
            assert started.wait(5), "first caller did not start serialization"
            assert bound.invoke("Analyze the market").content == "report"
            assert "_serialized" in llm.__dict__
        finally:
            release.set()
        assert first.result(timeout=5).content == "report"


@pytest.mark.unit
def test_snapshot_iteration_preserves_fields_and_secret_redaction():
    llm = NormalizedChatOpenAI(model="gpt-4o-mini", api_key="test-key")
    assert dict(llm) == dict(BaseModel.__iter__(llm))
    serialized = dumpd(llm)
    assert serialized["kwargs"]["openai_api_key"]["type"] == "secret"
    assert "_serialized" not in dict(llm)
