import frappe
from anthropic import AsyncAnthropic
from frappe import _


def get_anthropic_client() -> AsyncAnthropic:
	"""
	Get the Anthropic client

	Async because the Agents SDK drives the model from an async runner; there is
	no sync path through this provider.
	"""

	raven_settings = frappe.get_cached_doc("Raven Settings")

	if not raven_settings.enable_ai_integration:
		frappe.throw(_("AI Integration is not enabled"))

	if not raven_settings.enable_anthropic_services:
		frappe.throw(_("Anthropic services are not enabled in Raven Settings"))

	api_key = raven_settings.get_password("anthropic_api_key")
	if not api_key:
		frappe.throw(_("Anthropic API key is not configured in Raven Settings"))

	return AsyncAnthropic(api_key=api_key.strip())


def get_anthropic_models() -> list[dict]:
	"""
	The models this key can actually use, newest first.

	Asked of the API rather than hardcoded, so a model released after this code
	was written shows up in the bot form without an app update — the same reason
	get_openai_models() lists rather than enumerates.
	"""
	import anthropic

	raven_settings = frappe.get_cached_doc("Raven Settings")
	api_key = raven_settings.get_password("anthropic_api_key")
	if not api_key:
		return []

	client = anthropic.Anthropic(api_key=api_key.strip())
	return [{"id": m.id, "display_name": getattr(m, "display_name", m.id)} for m in client.models.list()]


# Claude has no equivalent of OpenAI's hosted file-search or code-interpreter
# tools, so a bot on this provider gets the Frappe function tools only. The bot
# form hides both options for Anthropic; this list exists so the reason is
# written down next to the provider it applies to.
UNSUPPORTED_HOSTED_TOOLS = ("file_search", "code_interpreter")
