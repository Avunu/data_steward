# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""Version restore, disabled until it is rewritten.

`Version.data` is a diff (`{"changed": [[field, old, new], ...], ...}`), not a
snapshot, so the old restore applied nothing to the document while still
marking the Version restored and reporting success. Both entry points now
refuse. The rewrite replays the diff's old values onto the live document
instead; the old implementation is in git history (`git show
ff88498:jailbreak/jailbreak/overrides/version.py`) if it is wanted for
reference.
"""

from typing import NoReturn

import frappe
from frappe import _
from frappe.core.doctype.version.version import Version as BaseVersion
from frappe.types import DF


def _restore_disabled() -> NoReturn:
	frappe.throw(_("Version restore is temporarily disabled"))
	raise AssertionError  # pragma: no cover - frappe.throw always raises


class Version(BaseVersion):
	"""Adds restore to Version, registered through `extend_doctype_class`."""

	# Custom Field from custom/version.json
	restored: DF.Check

	@frappe.whitelist()
	def restore(self, alert: bool = True) -> str:
		"""Restore the document to this version. Disabled: see the module docstring."""
		del alert  # kept in the signature for desk callers; unused while disabled
		_restore_disabled()


@frappe.whitelist()
def bulk_restore(docnames: str | list[str]) -> dict:
	"""Restore several versions. Disabled along with `Version.restore`."""
	del docnames  # kept in the signature for desk callers; unused while disabled
	_restore_disabled()
