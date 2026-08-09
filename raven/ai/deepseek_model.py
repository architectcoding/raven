"""DeepSeek as an OpenAI-Agents-SDK model, via the SDK's LiteLLM adapter.

Same shape and same reasoning as `gemini_model.py`: DeepSeek's API is
OpenAI-compatible, so it does not need the bespoke provider Claude required, and
routing through LiteLLM picks up the handling the SDK already has — notably
`reasoning_content`, which `deepseek-reasoner` returns and which the converter
turns into a reasoning item rather than leaking into the reply text.

Going through LiteLLM rather than pointing `OpenAIProvider` at
api.deepseek.com is deliberate for the same reason as Gemini: the Local LLM
branch that would otherwise serve this bypasses the Agents loop and hand-rolls
tool calling.
"""

from __future__ import annotations

from agents.extensions.models.litellm_model import LitellmModel
from agents.models.interface import Model, ModelProvider

from raven.ai.deepseek_client import DEFAULT_MODEL

# LiteLLM routes on this prefix.
LITELLM_PREFIX = "deepseek/"


class DeepSeekProvider(ModelProvider):
	def __init__(self, api_key: str):
		self.api_key = api_key

	def get_model(self, model_name: str | None) -> Model:
		name = (model_name or DEFAULT_MODEL).strip()

		# The bot form stores a bare id like "deepseek-chat"; without the prefix
		# LiteLLM cannot tell which provider it is being asked for.
		if not name.startswith(LITELLM_PREFIX):
			name = f"{LITELLM_PREFIX}{name}"

		return LitellmModel(model=name, api_key=self.api_key)
