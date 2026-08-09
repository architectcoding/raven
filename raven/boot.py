import frappe


def boot_session(bootinfo):

	raven_settings = frappe.get_single("Raven Settings")

	bootinfo.show_raven_chat_on_desk = raven_settings.show_raven_on_desk

	document_link_override = frappe.get_hooks("raven_document_link_override")

	if frappe.session.user and frappe.session.user != "Guest":
		chat_style = frappe.db.get_value("Raven User", frappe.session.user, "chat_style")
	else:
		chat_style = "Simple"

	if document_link_override and len(document_link_override) > 0:
		bootinfo.raven_document_link_override = True

	# tenor_api_key is deliberately no longer sent to the client. Google shut the
	# Tenor API down on 2026-06-30 and stopped issuing keys in January 2026, so
	# neither a configured key nor the public fallback that used to live here can
	# work — it was a hardcoded credential for a dead service on every page load.
	# The Raven Settings field is kept (hidden) so existing values are not lost.

	bootinfo.chat_style = chat_style if chat_style else "Simple"

	bootinfo.push_notification_service = (
		raven_settings.push_notification_service
		if raven_settings.push_notification_service
		else "Frappe Cloud"
	)

	if raven_settings.push_notification_service == "Raven":
		bootinfo.vapid_public_key = raven_settings.vapid_public_key
		bootinfo.firebase_client_config = raven_settings.config
