"""The app switcher in Raven's header and rail, filled by whichever suite Raven
is installed beside -- Raven never imports it.

An app answers the `raven_app_switcher` hook with the dotted path of a function
returning the apps the session user may open:

    # hooks.py of the suite app
    raven_app_switcher = "suite.api.get_launcher_apps"   # -> [{key, label, route, icon}]

The last app to answer wins. With no answer the list is empty and the switcher
is not drawn, so Raven runs exactly as upstream.
"""

import frappe


def has_provider():
	return bool(frappe.get_hooks("raven_app_switcher"))


@frappe.whitelist()
def get_app_switcher():
	paths = frappe.get_hooks("raven_app_switcher") or []
	if not paths:
		return []
	try:
		apps = frappe.get_attr(paths[-1])() or []
	except Exception:
		# A broken provider costs the switcher, never the page.
		frappe.log_error(title="raven_app_switcher failed")
		return []
	out = []
	for a in apps:
		route = str(a.get("route") or "")
		# Same-site paths only: the list is rendered as links in this app.
		if not route.startswith("/") or route.startswith("//"):
			continue
		out.append(
			{
				"key": str(a.get("key") or ""),
				"label": str(a.get("label") or ""),
				"route": route,
				"icon": str(a.get("icon") or "grid"),
			}
		)
	return out
