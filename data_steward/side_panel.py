# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""The server half of the editable desk side panel (`public/js/side_panel.js`).

Frappe's preview (`frappe.desk.doc_preview.get_preview`) is extended with the permlevels the
user may change, and the panel's edits come back to `save`, which writes only the changed
fields through a normal `Document.save`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.desk import doc_preview
from frappe.model import no_value_fields

if TYPE_CHECKING:
	from frappe.model.document import Document


def get_write_permlevels(doc: Document) -> list[int]:
	"""The permlevels a plain save lets the user change: none on a cancelled document, and on a
	submitted one only with submit permission, which an update after submit also needs
	(`Document.check_docstatus_transition`). The panel still applies the form's own rules per
	field: read only, allow on submit, set only once."""
	if doc.docstatus.is_cancelled() or not doc.has_permission("write"):
		return []
	if doc.docstatus.is_submitted() and not doc.has_permission("submit"):
		return []
	return doc.get_permlevel_access("write")


@frappe.whitelist(methods=["GET"])
def get_preview(doctype: str, name: str) -> dict[str, Any]:
	"""Replaces `frappe.desk.doc_preview.get_preview` (hooks.py): Frappe's preview, plus
	`write_permlevels`, the permlevels whose fields the user may change."""
	preview = doc_preview.get_preview(doctype, name)
	preview["write_permlevels"] = get_write_permlevels(frappe.get_doc(doctype, name))
	return preview


@frappe.whitelist(methods=["POST"])
def save(doctype: str, name: str, values: str | dict[str, Any], modified: str) -> dict[str, Any]:
	"""Saves the fields changed in the side panel and returns the document's new preview.

	`modified` is the timestamp of the copy the panel showed. It becomes the document's
	`modified` for the save, so Frappe's `check_if_latest` refuses it when someone else has
	saved the document since, as it does for the form.
	"""
	values = frappe.parse_json(values) if isinstance(values, str) else values
	if not isinstance(values, dict):
		frappe.throw(_("The changed values must be an object of fieldnames."))

	doc = frappe.get_doc(doctype, name)

	for fieldname in values:
		df = doc.meta.get_field(fieldname)
		# Only plain fields: standard fields (docstatus, owner…) are not meta fields, and child
		# tables are edited in the form.
		if not df or df.fieldtype in no_value_fields:
			frappe.throw(
				_("{0} cannot be changed from the side panel.").format(frappe.bold(fieldname)),
				title=_("Not Saved"),
			)

	doc.update(values)
	doc.modified = modified
	doc.save()
	return get_preview(doctype, name)
