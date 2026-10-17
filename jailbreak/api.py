import frappe

from jailbreak.jailbreak.doctype.jailbreak_settings.jailbreak_settings import (
	capability_name,
)


@frappe.whitelist()
def assert_capability(capability: capability_name) -> None:
	from jailbreak.jailbreak.doctype.jailbreak_settings.jailbreak_settings import (
		assert_capability as _assert_capability,
	)

	return _assert_capability(capability)


@frappe.whitelist()
def check_capability(capability: capability_name) -> bool:
	from jailbreak.jailbreak.doctype.jailbreak_settings.jailbreak_settings import (
		check_capability as _check_capability,
	)

	return _check_capability(capability)
