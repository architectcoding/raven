import frappe
from frappe import _

# Used when the live list can't be fetched, so the bot form's dropdown is never
# empty. DeepSeek publishes a small, stable model set, so unlike Gemini this is
# close to the whole catalogue rather than a token sample.
FALLBACK_MODELS = ["deepseek-chat", "deepseek-reasoner"]

# deepseek-reasoner (R1) is a reasoning model and has historically not supported
# function calling. A Raven bot is mostly tool calls, so the default is the chat
# model; reasoner is still selectable for bots that only answer from their
# instructions.
DEFAULT_MODEL = "deepseek-chat"


def get_deepseek_api_key() -> str:
	raven_settings = frappe.get_cached_doc("Raven Settings")

	if not raven_settings.enable_ai_integration:
		frappe.throw(_("AI Integration is not enabled"))

	if not raven_settings.enable_deepseek_services:
		frappe.throw(_("DeepSeek is not enabled in Raven Settings"))

	# raise_exception=False: an unset password field throws, which would turn
	# "not configured yet" into a logged error while someone is still filling in
	# the form.
	api_key = raven_settings.get_password("deepseek_api_key", raise_exception=False)
	if not api_key:
		frappe.throw(_("DeepSeek API key is not configured in Raven Settings"))

	return api_key.strip()


def get_deepseek_models() -> list[str]:
	"""
	Models this key can use. DeepSeek exposes an OpenAI-shaped /models endpoint.
	"""
	import requests

	raven_settings = frappe.get_cached_doc("Raven Settings")
	api_key = raven_settings.get_password("deepseek_api_key", raise_exception=False)
	if not api_key:
		return FALLBACK_MODELS

	try:
		response = requests.get(
			"https://api.deepseek.com/models",
			headers={"Authorization": f"Bearer {api_key.strip()}"},
			timeout=10,
		)
		response.raise_for_status()
		models = [m.get("id") for m in response.json().get("data", []) if m.get("id")]
	except Exception as e:
		frappe.log_error(f"Could not list DeepSeek models: {e}", "DeepSeek Models Error")
		return FALLBACK_MODELS

	return sorted(models) or FALLBACK_MODELS
