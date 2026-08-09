"""Anthropic stream events -> ChatCompletionChunk, for the SDK's stream handler.

`ChatCmplStreamHandler.handle_stream` assembles Responses-API stream events out
of Chat Completions chunks. It only ever does `async for chunk in stream`, so a
plain async generator is enough — it does not need a real `AsyncStream`.

Untested against Raven, which never streams its agent path (`Runner.run()`
only; the streaming in handler.py is the legacy Assistants API). Written to the
documented shapes rather than proven in situ.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import (
	Choice,
	ChoiceDelta,
	ChoiceDeltaToolCall,
	ChoiceDeltaToolCallFunction,
)
from openai.types.completion_usage import CompletionUsage


def _chunk(model: str, delta: ChoiceDelta, finish_reason: str | None = None, usage=None):
	return ChatCompletionChunk(
		id="anthropic-stream",
		created=0,
		model=model,
		object="chat.completion.chunk",
		choices=[Choice(index=0, delta=delta, finish_reason=finish_reason)],
		usage=usage,
	)


async def anthropic_chunks(stream: Any, model: str) -> AsyncIterator[ChatCompletionChunk]:
	"""Translate one Anthropic message stream into Chat Completions chunks."""
	# Anthropic indexes tool_use blocks within the message; Chat Completions
	# indexes tool calls within the turn. They line up 1:1 per block, so the
	# block index doubles as the tool-call index.
	tool_indexes: dict[int, int] = {}
	next_tool_index = 0
	input_tokens = 0
	output_tokens = 0

	async for event in stream:
		event_type = getattr(event, "type", None)

		if event_type == "message_start":
			usage = getattr(getattr(event, "message", None), "usage", None)
			input_tokens = getattr(usage, "input_tokens", 0) or 0
			continue

		if event_type == "content_block_start":
			block = getattr(event, "content_block", None)
			if getattr(block, "type", None) == "tool_use":
				index = next_tool_index
				tool_indexes[event.index] = index
				next_tool_index += 1
				yield _chunk(
					model,
					ChoiceDelta(
						tool_calls=[
							ChoiceDeltaToolCall(
								index=index,
								id=block.id,
								type="function",
								function=ChoiceDeltaToolCallFunction(name=block.name, arguments=""),
							)
						]
					),
				)
			continue

		if event_type == "content_block_delta":
			delta = getattr(event, "delta", None)
			delta_type = getattr(delta, "type", None)

			if delta_type == "text_delta":
				yield _chunk(model, ChoiceDelta(content=delta.text))
			elif delta_type == "thinking_delta":
				# `reasoning_content` is the field the SDK's handler recognises for
				# non-OpenAI reasoning models.
				chunk = _chunk(model, ChoiceDelta(content=None))
				chunk.choices[0].delta.reasoning_content = delta.thinking  # type: ignore[attr-defined]
				yield chunk
			elif delta_type == "input_json_delta":
				index = tool_indexes.get(event.index)
				if index is not None:
					yield _chunk(
						model,
						ChoiceDelta(
							tool_calls=[
								ChoiceDeltaToolCall(
									index=index,
									function=ChoiceDeltaToolCallFunction(arguments=delta.partial_json),
								)
							]
						),
					)
			continue

		if event_type == "message_delta":
			usage = getattr(event, "usage", None)
			output_tokens = getattr(usage, "output_tokens", 0) or output_tokens
			stop_reason = getattr(getattr(event, "delta", None), "stop_reason", None)
			finish = {
				"end_turn": "stop",
				"max_tokens": "length",
				"stop_sequence": "stop",
				"tool_use": "tool_calls",
				"refusal": "content_filter",
			}.get(stop_reason or "", "stop")
			yield _chunk(
				model,
				ChoiceDelta(),
				finish_reason=finish,
				usage=CompletionUsage(
					prompt_tokens=input_tokens,
					completion_tokens=output_tokens,
					total_tokens=input_tokens + output_tokens,
				),
			)
			continue


def json_or_empty(raw: str) -> dict:
	try:
		return json.loads(raw or "{}")
	except json.JSONDecodeError:
		return {}
