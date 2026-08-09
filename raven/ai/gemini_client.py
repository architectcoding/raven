import frappe
from frappe import _

# Shown when the live model list can't be fetched, so the bot form's dropdown is
# never empty. Floating aliases only: Google retires pinned ids for new API keys
# (a fresh key gets 404 "no longer available to new users" on gemini-2.5-flash),
# so a hardcoded pinned id is a fallback that ages into a broken default.
FALLBACK_MODELS = [
	"gemini-flash-latest",
	"gemini-flash-lite-latest",
	"gemini-pro-latest",
]


def get_gemini_api_key() -> str:
	"""
	The Gemini API key, or a clear error saying which switch is off.

	Note this is *not* the Google credential the OCR integration uses:
	`google_service_account_json_key` is a service account for Vision and
	Document AI. This one is an AI Studio key for the Gemini models.
	"""

	raven_settings = frappe.get_cached_doc("Raven Settings")

	if not raven_settings.enable_ai_integration:
		frappe.throw(_("AI Integration is not enabled"))

	if not raven_settings.enable_gemini_services:
		frappe.throw(_("Google Gemini is not enabled in Raven Settings"))

	api_key = raven_settings.get_password("gemini_api_key")
	if not api_key:
		frappe.throw(_("Gemini API key is not configured in Raven Settings"))

	return api_key.strip()


def get_gemini_models() -> list[str]:
	"""
	Models this key can use, asked of Google so a newly released one is
	selectable without shipping a new Raven build.

	Only models that can actually hold a conversation are returned — the same
	endpoint also lists embedding and image models, which would fail the moment
	someone picked one for a bot.
	"""
	import requests

	try:
		api_key = get_gemini_api_key()
	except Exception:
		return FALLBACK_MODELS

	try:
		response = requests.get(
			"https://generativelanguage.googleapis.com/v1beta/models",
			params={"key": api_key},
			timeout=10,
		)
		response.raise_for_status()
		models = response.json().get("models", [])
	except Exception as e:
		frappe.log_error(f"Could not list Gemini models: {e}", "Gemini Models Error")
		return FALLBACK_MODELS

	usable = []
	for model in models:
		# "models/gemini-flash-latest" -> "gemini-flash-latest"
		name = (model.get("name") or "").removeprefix("models/")
		if not name.startswith("gemini-"):
			continue
		if "generateContent" not in (model.get("supportedGenerationMethods") or []):
			continue
		usable.append(name)

	# Floating aliases first. This list is not a promise that every entry works:
	# Google keeps returning pinned ids that then 404 for newer API keys with
	# "no longer available to new users". The aliases always resolve to something
	# current, so surfacing them at the top means the first thing a person picks
	# is the thing most likely to answer.
	usable.sort(key=lambda name: (not name.endswith("-latest"), name))

	return usable or FALLBACK_MODELS
