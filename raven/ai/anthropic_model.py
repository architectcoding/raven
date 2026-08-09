"""Claude as an OpenAI-Agents-SDK model.

The Agents SDK talks to models through its `Model` interface, and its whole
non-OpenAI story routes through the Chat Completions shape: `Converter` turns
agent items into ChatCompletions messages on the way in and back into agent
items on the way out. `LitellmModel` in the SDK works exactly this way. Doing
the same here buys ~1,700 lines of tested conversion (tool calls, tool results,
reasoning items, streaming assembly) instead of hand-rolling the agent item
protocol against Anthropic's wire format.

To be clear about what that does and does not mean: the ChatCompletions objects
below never leave this process. The network call is
`AsyncAnthropic().messages.create()` — the official SDK, Anthropic's own wire
format. No OpenAI-compatible endpoint is involved.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import frappe
from agents import ModelSettings, Tool
from agents.agent_output import AgentOutputSchemaBase
from agents.handoffs import Handoff
from agents.items import ModelResponse, TResponseInputItem, TResponseStreamEvent
from agents.models.chatcmpl_converter import Converter
from agents.models.chatcmpl_stream_handler import ChatCmplStreamHandler
from agents.models.fake_id import FAKE_RESPONSES_ID
from agents.models.interface import Model, ModelProvider, ModelTracing
from agents.usage import Usage
from anthropic import AsyncAnthropic
from openai.types.chat import ChatCompletionMessage
from openai.types.chat.chat_completion_message_function_tool_call import Function
from openai.types.chat.chat_completion_message_function_tool_call import (
	ChatCompletionMessageFunctionToolCall,
)
from openai.types.responses import Response

from raven.ai.anthropic_client import get_anthropic_client

# Anthropic requires max_tokens on every request (OpenAI does not). It also caps
# thinking AND visible text together, so a tight budget truncates mid-answer on a
# thinking model. Generous by default; the bot can override.
DEFAULT_MAX_TOKENS = 16000

# Claude's effort ladder. Raven's reasoning_effort field carries low/medium/high
# from its OpenAI days; xhigh and max are Claude-only additions.
VALID_EFFORTS = {"low", "medium", "high", "xhigh", "max"}

# Model families that reject `effort` rather than ignoring it. Matched as
# substrings so a future dated id in the same family is covered. Expressed as a
# denylist because the models that DO take it are the growing set — a new Opus or
# Sonnet should work on the day it ships without editing this file.
NO_EFFORT_SUPPORT = ("haiku", "sonnet-4-5")


def model_supports_effort(model: str) -> bool:
	name = (model or "").lower()
	return not any(marker in name for marker in NO_EFFORT_SUPPORT)


class AnthropicChatMessage(ChatCompletionMessage):
	"""Carries Claude's thinking blocks through the ChatCompletions interchange.

	`Converter` looks for `reasoning_content` and `thinking_blocks` by `hasattr`
	(it cannot import LiteLLM's equivalent class, which is optional), turns them
	into a reasoning item on the way out, and reconstitutes them on the way back
	in when `preserve_thinking_blocks=True`. Signatures ride along in
	`encrypted_content`, which is what lets a multi-turn tool-calling
	conversation replay its thinking to Claude unmodified — the API rejects
	edited thinking blocks.
	"""

	reasoning_content: str
	thinking_blocks: list[dict[str, Any]] | None = None


class AnthropicModel(Model):
	def __init__(self, model: str, client: AsyncAnthropic, bot_doc=None):
		self.model = model
		self.client = client
		self.bot_doc = bot_doc

	# --- request building --------------------------------------------------
	@property
	def _max_tokens(self) -> int:
		value = getattr(self.bot_doc, "max_tokens", None) if self.bot_doc else None
		return int(value) if value else DEFAULT_MAX_TOKENS

	@property
	def _effort(self) -> str | None:
		value = (getattr(self.bot_doc, "reasoning_effort", None) or "").strip().lower()
		if value not in VALID_EFFORTS:
			return None

		# Not every Claude model takes `effort` — Haiku 4.5 and Sonnet 4.5 reject
		# it outright, so sending it because the bot happens to have the field set
		# would 400 every request on those models rather than degrade. The field is
		# shared with the OpenAI provider, so it can easily be populated on a bot
		# that later switches to Haiku.
		if not model_supports_effort(self.model):
			return None

		return value

	def _build_kwargs(
		self,
		system_instructions: str | None,
		input: str | list[TResponseInputItem],
		tools: list[Tool],
		handoffs: list[Handoff],
	) -> dict[str, Any]:
		messages = Converter.items_to_messages(
			input,
			model=self.model,
			# Claude requires thinking blocks to come back unchanged across turns
			# of a tool-calling conversation. Without this the replay is missing
			# them and the API rejects the request.
			preserve_thinking_blocks=True,
			preserve_tool_output_all_content=True,
		)

		system_blocks, anthropic_messages = self._split_messages(system_instructions, messages)

		converted_tools = [Converter.tool_to_openai(t) for t in tools] if tools else []
		converted_tools += [Converter.convert_handoff_tool(h) for h in handoffs]

		kwargs: dict[str, Any] = {
			"model": self.model,
			"max_tokens": self._max_tokens,
			"messages": anthropic_messages,
		}

		if system_blocks:
			kwargs["system"] = system_blocks
		if converted_tools:
			kwargs["tools"] = [self._tool_to_anthropic(t) for t in converted_tools]
		if self._effort:
			kwargs["output_config"] = {"effort": self._effort}

		# NOTE: temperature / top_p / top_k are deliberately never sent. Raven
		# always populates ModelSettings with temperature and top_p (both default
		# to 1 on Raven Bot), and Claude Opus 5, Sonnet 5 and Opus 4.7/4.8 removed
		# those parameters — every request carrying them fails with a 400. Reading
		# them off model_settings here is the single most likely way to
		# reintroduce that bug, so this provider ignores them by construction.
		return kwargs

	def _split_messages(
		self, system_instructions: str | None, messages: list[dict]
	) -> tuple[list[dict], list[dict]]:
		"""Pull `system` out to the top level and normalise the rest for Anthropic.

		Three shape differences from Chat Completions have to be reconciled:
		system is a request field rather than a message, tool results are content
		blocks on a *user* message rather than their own role, and the message
		list must alternate starting with user.
		"""
		system_texts: list[str] = []
		if system_instructions:
			system_texts.append(system_instructions)

		converted: list[dict] = []
		for message in messages:
			role = message.get("role")

			if role == "system":
				text = _text_of(message.get("content"))
				if text:
					system_texts.append(text)
				continue

			if role == "tool":
				converted.append(
					{
						"role": "user",
						"content": [
							{
								"type": "tool_result",
								"tool_use_id": message.get("tool_call_id"),
								"content": _text_of(message.get("content")) or "",
							}
						],
					}
				)
				continue

			if role == "assistant":
				blocks = self._assistant_blocks(message)
				if blocks:
					converted.append({"role": "assistant", "content": blocks})
				continue

			blocks = _user_blocks(message.get("content"))
			if blocks:
				converted.append({"role": "user", "content": blocks})

		system_blocks = []
		if system_texts:
			# One breakpoint on the last system block. Raven appends a large,
			# static tool-instruction preamble to every request and it is identical
			# for the life of a channel, which is exactly the shape prompt caching
			# is for.
			system_blocks = [{"type": "text", "text": "\n\n".join(system_texts)}]
			system_blocks[-1]["cache_control"] = {"type": "ephemeral"}

		return system_blocks, _normalise_turns(converted)

	def _assistant_blocks(self, message: dict) -> list[dict]:
		blocks: list[dict] = []

		# Thinking must come first in the assistant turn, and must be replayed
		# byte-identical — hence carrying the signature through rather than
		# rebuilding the block from its text.
		for block in message.get("thinking_blocks") or []:
			if isinstance(block, dict) and block.get("signature"):
				blocks.append(
					{
						"type": "thinking",
						"thinking": block.get("thinking", ""),
						"signature": block["signature"],
					}
				)

		text = _text_of(message.get("content"))
		if text:
			blocks.append({"type": "text", "text": text})

		for call in message.get("tool_calls") or []:
			function = call.get("function", {}) if isinstance(call, dict) else {}
			raw_args = function.get("arguments") or "{}"
			try:
				arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
			except json.JSONDecodeError:
				arguments = {}
			blocks.append(
				{
					"type": "tool_use",
					"id": call.get("id"),
					"name": function.get("name"),
					"input": arguments,
				}
			)

		return blocks

	def _tool_to_anthropic(self, tool: dict) -> dict:
		function = tool.get("function", tool)
		return {
			"name": function.get("name"),
			"description": function.get("description") or "",
			"input_schema": function.get("parameters") or {"type": "object", "properties": {}},
		}

	# --- response conversion ------------------------------------------------
	def _to_chat_message(self, response) -> AnthropicChatMessage:
		text_parts: list[str] = []
		thinking_parts: list[str] = []
		thinking_blocks: list[dict[str, Any]] = []
		tool_calls: list[ChatCompletionMessageFunctionToolCall] = []

		for block in response.content or []:
			block_type = getattr(block, "type", None)
			if block_type == "text":
				text_parts.append(block.text)
			elif block_type == "thinking":
				thinking_parts.append(getattr(block, "thinking", "") or "")
				thinking_blocks.append(
					{
						"type": "thinking",
						"thinking": getattr(block, "thinking", "") or "",
						"signature": getattr(block, "signature", None),
					}
				)
			elif block_type == "tool_use":
				tool_calls.append(
					ChatCompletionMessageFunctionToolCall(
						id=block.id,
						type="function",
						function=Function(name=block.name, arguments=json.dumps(block.input or {})),
					)
				)

		return AnthropicChatMessage(
			role="assistant",
			content="".join(text_parts) or None,
			tool_calls=tool_calls or None,
			reasoning_content="\n".join(p for p in thinking_parts if p),
			thinking_blocks=thinking_blocks or None,
		)

	def _usage(self, response) -> Usage:
		usage = getattr(response, "usage", None)
		if not usage:
			return Usage(requests=1)
		input_tokens = getattr(usage, "input_tokens", 0) or 0
		output_tokens = getattr(usage, "output_tokens", 0) or 0
		return Usage(
			requests=1,
			input_tokens=input_tokens,
			output_tokens=output_tokens,
			total_tokens=input_tokens + output_tokens,
		)

	# --- Model interface ----------------------------------------------------
	async def get_response(
		self,
		system_instructions: str | None,
		input: str | list[TResponseInputItem],
		model_settings: ModelSettings,
		tools: list[Tool],
		output_schema: AgentOutputSchemaBase | None,
		handoffs: list[Handoff],
		tracing: ModelTracing,
		*,
		previous_response_id: str | None = None,
		conversation_id: str | None = None,
		prompt: Any | None = None,
	) -> ModelResponse:
		kwargs = self._build_kwargs(system_instructions, input, tools, handoffs)
		response = await self.client.messages.create(**kwargs)

		# A safety classifier can decline the request: HTTP 200, no usable
		# content. Checking stop_reason before reading content is what keeps this
		# from surfacing as an IndexError somewhere further down.
		if response.stop_reason == "refusal":
			frappe.log_error(
				f"Claude declined the request.\nModel: {self.model}\n"
				f"Details: {getattr(response, 'stop_details', None)}",
				"Anthropic Refusal",
			)
			message = AnthropicChatMessage(
				role="assistant",
				content=frappe._("The model declined to respond to this request."),
				reasoning_content="",
			)
			return ModelResponse(
				output=Converter.message_to_output_items(message),
				usage=self._usage(response),
				response_id=response.id,
			)

		message = self._to_chat_message(response)
		return ModelResponse(
			output=Converter.message_to_output_items(message),
			usage=self._usage(response),
			response_id=response.id,
		)

	async def stream_response(
		self,
		system_instructions: str | None,
		input: str | list[TResponseInputItem],
		model_settings: ModelSettings,
		tools: list[Tool],
		output_schema: AgentOutputSchemaBase | None,
		handoffs: list[Handoff],
		tracing: ModelTracing,
		*,
		previous_response_id: str | None = None,
		conversation_id: str | None = None,
		prompt: Any | None = None,
	) -> AsyncIterator[TResponseStreamEvent]:
		"""Streaming, via the SDK's own chunk assembler.

		Raven does not exercise this today — its agent path is `Runner.run()`,
		and the streaming in handler.py belongs to the legacy Assistants API — so
		treat it as untested rather than proven.
		"""
		from raven.ai.anthropic_stream import anthropic_chunks

		kwargs = self._build_kwargs(system_instructions, input, tools, handoffs)
		response = Response(
			id=FAKE_RESPONSES_ID,
			created_at=0,
			model=self.model,
			object="response",
			output=[],
			tool_choice="auto",
			tools=[],
			parallel_tool_calls=False,
		)

		async with self.client.messages.stream(**kwargs) as stream:
			async for event in ChatCmplStreamHandler.handle_stream(
				response, anthropic_chunks(stream, self.model)
			):
				yield event


class AnthropicProvider(ModelProvider):
	def __init__(self, client: AsyncAnthropic, bot_doc=None):
		self.client = client
		self.bot_doc = bot_doc

	def get_model(self, model_name: str | None) -> Model:
		return AnthropicModel(
			model=model_name or "claude-opus-5", client=self.client, bot_doc=self.bot_doc
		)


# --- helpers ---------------------------------------------------------------
def _text_of(content) -> str:
	"""Chat Completions content is either a string or a list of parts."""
	if content is None:
		return ""
	if isinstance(content, str):
		return content
	if isinstance(content, list):
		parts = []
		for part in content:
			if isinstance(part, str):
				parts.append(part)
			elif isinstance(part, dict) and part.get("type") in ("text", "input_text", "output_text"):
				parts.append(part.get("text") or "")
		return "".join(parts)
	return str(content)


def _user_blocks(content) -> list[dict]:
	"""User content, keeping images as image blocks rather than flattening them."""
	if isinstance(content, str):
		return [{"type": "text", "text": content}] if content else []

	blocks: list[dict] = []
	for part in content or []:
		if isinstance(part, str):
			if part:
				blocks.append({"type": "text", "text": part})
			continue
		if not isinstance(part, dict):
			continue
		part_type = part.get("type")
		if part_type in ("text", "input_text"):
			if part.get("text"):
				blocks.append({"type": "text", "text": part["text"]})
		elif part_type in ("image_url", "input_image"):
			url = part.get("image_url", {}).get("url") if isinstance(part.get("image_url"), dict) else None
			url = url or part.get("image_url") or part.get("image")
			if isinstance(url, str) and url.startswith("data:"):
				header, _, data = url.partition(",")
				media_type = header.split(";")[0].removeprefix("data:") or "image/png"
				blocks.append(
					{
						"type": "image",
						"source": {"type": "base64", "media_type": media_type, "data": data},
					}
				)
			elif isinstance(url, str) and url:
				blocks.append({"type": "image", "source": {"type": "url", "url": url}})
	return blocks


def _normalise_turns(messages: list[dict]) -> list[dict]:
	"""Make the list satisfy Anthropic's alternation rules.

	Chat Completions tolerates a leading assistant turn and consecutive turns
	from the same role; Anthropic requires the conversation to start with `user`
	and to alternate. Raven's own history builder produces both — it replays
	stored channel messages verbatim, which can begin with a bot reply.
	"""
	out: list[dict] = []
	for message in messages:
		if not out and message["role"] == "assistant":
			# Nothing for the assistant to have replied to yet.
			continue
		if out and out[-1]["role"] == message["role"]:
			out[-1]["content"] = list(out[-1]["content"]) + list(message["content"])
			continue
		out.append(dict(message))

	if not out:
		# Anthropic rejects an empty conversation; the Agents SDK can legitimately
		# hand us one when every history item was filtered out above.
		out = [{"role": "user", "content": [{"type": "text", "text": "(no message)"}]}]
	return out
