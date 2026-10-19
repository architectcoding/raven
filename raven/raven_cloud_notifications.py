import json
from urllib.parse import urlparse

import frappe

from raven.utils import make_api_call

# ----- Utility Functions -----


def get_site_name():
	return urlparse(frappe.utils.get_url()).hostname


# ----- Token Management -----


def add_token_to_raven_cloud(user_id, token):
	"""
	Add a token to Raven Cloud
	"""
	raven_settings = frappe.get_single("Raven Settings")

	url = f"{raven_settings.push_notification_server_url}/api/method/raven_cloud.api.notification.create_user_token"

	make_api_call(
		url=url,
		api_key=raven_settings.push_notification_api_key,
		api_secret=raven_settings.get_password("push_notification_api_secret"),
		method="POST",
		params={
			"user_id": user_id,
			"token": token,
			"site_name": get_site_name(),
		},
	)


def delete_token_from_raven_cloud(user_id, token):
	"""
	Delete a token from Raven Cloud
	"""
	raven_settings = frappe.get_single("Raven Settings")

	url = f"{raven_settings.push_notification_server_url}/api/method/raven_cloud.api.notification.delete_user_token"

	make_api_call(
		url=url,
		api_key=raven_settings.push_notification_api_key,
		api_secret=raven_settings.get_password("push_notification_api_secret"),
		method="POST",
		params={
			"user_id": user_id,
			"token": token,
			"site_name": get_site_name(),
		},
	)


def sync_users_tokens_to_raven_cloud():
	"""
	Sync all the tokens available on this site to Raven Cloud
	"""
	raven_settings = frappe.get_single("Raven Settings")
	# Daily maintenance runs this on every site, but only a site that pushes
	# through Raven Cloud has a server URL, key and secret to sync with. On a
	# "Frappe Cloud" site get_password raised "Password not found" every night.
	if not _uses_raven_cloud(raven_settings):
		return "Raven Cloud is not the push notification service"
	tokens = frappe.db.get_all("Raven Push Token", fields=["user", "fcm_token"], order_by="user")

	url = f"{raven_settings.push_notification_server_url}/api/method/raven_cloud.api.notification.import_user_tokens"

	response = make_api_call(
		url=url,
		api_key=raven_settings.push_notification_api_key,
		api_secret=raven_settings.get_password("push_notification_api_secret"),
		method="POST",
		params={"site_name": get_site_name(), "tokens": json.dumps(tokens)},
	)
	message = response.get("message")

	if message.get("status") == "success":
		return "Tokens synced successfully"
	else:
		frappe.log_error(
			title="Raven Cloud Sync Tokens Error",
			message=f"Failed to sync tokens: {message.get('message')}",
		)
		return "Failed to sync tokens"


def _uses_raven_cloud(raven_settings):
	return (
		raven_settings.push_notification_service == "Raven"
		and raven_settings.push_notification_server_url
		and raven_settings.push_notification_api_key
		and raven_settings.get_password("push_notification_api_secret", raise_exception=False)
	)
