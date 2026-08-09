"""Gemini as an OpenAI-Agents-SDK model, via the SDK's LiteLLM adapter.

Deliberately not a bespoke provider like `anthropic_model.py`, and the reason
is worth keeping written down. Claude needed one because the Chat Completions
path cannot express its requirements — it rejects `temperature`/`top_p`, and its
thinking blocks have to be replayed with their signatures. Gemini's requirements
*are* expressible there, and the SDK already ships the awkward parts:

* `_convert_gemini_extra_content_to_provider_specific_fields` round-trips
  Gemini's **thought signatures**, which 2.5+ requires echoed back during
  multi-turn function calling or the request errors.
* `ChatCmplHelpers.clean_gemini_tool_call_id` handles Gemini's tool-call id
  constraints, which differ from OpenAI's.
* Message reordering is applied for gemini the same way it is for claude.

Those exist because the naive path breaks. Reusing them beats rediscovering
them, so this file is thin on purpose.
"""

from __future__ import annotations

from agents.extensions.models.litellm_model import LitellmModel
from agents.models.interface import Model, ModelProvider

# Flash is the sensible default: cheapest, fast, and comfortably good enough for
# the document lookups Raven bots actually do.
DEFAULT_MODEL = "gemini-2.5-flash"

# LiteLLM routes on this prefix — it is what selects the Gemini path and, with
# it, the quirk handling described above.
LITELLM_PREFIX = "gemini/"


class GeminiProvider(ModelProvider):
	def __init__(self, api_key: str):
		self.api_key = api_key

	def get_model(self, model_name: str | None) -> Model:
		name = (model_name or DEFAULT_MODEL).strip()

		# Normalise here rather than trusting the stored value: the bot form
		# saves a bare id like "gemini-2.5-flash", and without the prefix LiteLLM
		# has no idea which provider it is being asked for.
		if not name.startswith(LITELLM_PREFIX):
			name = f"{LITELLM_PREFIX}{name}"

		return LitellmModel(model=name, api_key=self.api_key)
