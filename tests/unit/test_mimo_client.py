"""MIMO gateway tests."""

from xiaotie.llm import MimoClient
from xiaotie.llm.providers import MIMO_DEFAULT_API_BASE, MIMO_DEFAULT_MODEL


def test_mimo_client_uses_mimo_defaults():
    client = MimoClient("test-key")
    assert client.api_base == MIMO_DEFAULT_API_BASE
    assert client.model == MIMO_DEFAULT_MODEL
