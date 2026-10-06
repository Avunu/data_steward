import json

import frappe
from frappe import _
from frappe.core.doctype.version.version import Version as BaseVersion
from frappe.desk.doctype.bulk_update.bulk_update import show_progress
from frappe.model.document import Document
from frappe.types import DF

from jailbreak import assert_capability


class Version(BaseVersion):
	"""Custom Version override to jailbreak with restore functionality."""

	# Custom fields from item.json
	restored: DF.Check

	@frappe.whitelist()
	def restore(self, alert: bool = True) -> str:
		"""Restore a version by creating a new document with the version data."""
		# Disabled: Version.data is a diff, not a snapshot, so this never
		# reverted anything while still reporting success. The code below is
		# kept as the starting point for the rewrite.
		frappe.throw(_("Version restore is temporarily disabled"))

		# Check if the version restore capability is enabled
		assert_capability("version_restore")

		# Check if the document exists
		if not frappe.db.exists(self.ref_doctype, self.docname):
			frappe.throw(_("Document {0} does not exist").format(self.docname))

		# Check if the version is already restored
		if self.restored:
			frappe.throw(
				_("Version {0} Already Restored").format(self.name),
				exc=frappe.DocumentAlreadyRestored,
			)

		# Parse the version data similar to deleted document
		version_data: dict
		data = self.data
		if isinstance(data, str):
			version_data = json.loads(data)
		else:
			frappe.throw(_("Invalid version data format"))

		# Update the document with version data
		doc: Document
		try:
			doc = frappe.get_doc(self.ref_doctype, self.docname)
			doc.update(version_data)

		except frappe.DocstatusTransitionError:
			frappe.msgprint(_("Cancelled Document restored as Draft"))
			doc.docstatus = 0
			doc.save()

		doc.add_comment("Edit", _("restored from version {0} as {1}").format(self.name, doc.name))

		# Mark version as restored
		self.set("restored", 1)
		self.db_update()

		if alert:
			frappe.msgprint(_("Version Restored as {0}").format(doc.name))

		return doc.name


@frappe.whitelist()
def bulk_restore(docnames: str | list[str]) -> dict:
	"""Bulk restore multiple versions."""
	# Disabled along with Version.restore - see there.
	frappe.throw(_("Version restore is temporarily disabled"))

	docnames = frappe.parse_json(docnames)
	message = _("Restoring Version")
	restored, invalid, failed = [], [], []

	for i, d in enumerate(docnames):
		try:
			show_progress(docnames, message, i + 1, d)
			version: Version = Version("Version", d)
			if version.restored:
				invalid.append(d)
				continue

			# Restore the version
			new_name = version.restore(alert=False)
			frappe.db.commit()
			restored.append({"version": d, "new_name": new_name})

		except frappe.DocumentAlreadyRestored:
			frappe.clear_last_message()
			invalid.append(d)

		except Exception:
			frappe.clear_last_message()
			failed.append(d)
			frappe.db.rollback()

	return {"restored": restored, "invalid": invalid, "failed": failed}
