# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""S2 coverage for the `Version` controller override - the app's namesake
"restore" feature.

**Now disabled.** Because of the pinned bug described below, `Version.restore()`
and `bulk_restore()` now throw "Version restore is temporarily disabled"
before doing anything, and the desk buttons are no longer added. The tests
below assert that; the original restore code is kept in place for the
rewrite. The history below is kept for whoever does it.

**Real bug found and pinned, not fixed** - needs a product decision, same
category as the other tiers' pinned findings (`Design.reindex()`,
`merge_legacy_designs()`, the artist reports' missing `docstatus` filter).

`Version.restore()` is adapted from Frappe's own `DeletedDocument.restore()`
(same shape: check-already-restored, `doc.update(version_data)`, catch
`DocstatusTransitionError`, `add_comment`, mark restored). But
`DeletedDocument.data` is a **full document snapshot** - `frappe.get_doc()`
on it builds a whole new document. `Version.data` (built by
`Version.set_diff()`, the framework's own automatic version tracking) is a
**diff**: `{"changed": [[field, old, new], ...], "added": [...], "removed":
[...], "row_changed": [...], ...}`. Nothing in this app ever writes a
Version with a flat field->value `data` shape (grepped: only Frappe's own
tracking ever creates a Version row here) - so `doc.update(version_data)`
is always handed a diff dict, tries to set `changed`/`added`/`removed`/
`row_changed`/`data_import`/`updater_reference` as if they were fields on
the target document, and none of them are. `doc.save()` then succeeds as a
near no-op: the field the user actually wants back never changes, `restored`
is still set to `1`, and the success alert fires - **restore silently does
nothing but look like it worked.** Pinned as
`test_restore_does_not_actually_revert_the_changed_field` below, the same
way `Design.reindex()`'s bug was pinned rather than patched: the real fix
(replay `changed`/`added`/`removed` onto the live document, or capture full
snapshots instead of diffs) is a design decision about what "restore" means
here, not something to decide inside a testing pass.

**A second real bug found and fixed, not pinned** - `bulk_restore()`'s loop
checked `if version.restored: invalid.append(d)` but fell through into
`version.restore(alert=False)` anyway instead of `continue`-ing. That call
immediately raises `DocumentAlreadyRestored` (the same check `restore()`
itself does), caught by the surrounding `except frappe.DocumentAlreadyRestored:`,
which appends `d` to `invalid` *again* - so a bulk-restore that includes one
already-restored Version reports it twice in `invalid` and once in neither
list is worse: nothing here made it wrong for the *other* rows, but the
caller (the "Restore" list-view action) shows the same docname flagged
invalid twice. Fixed with the missing `continue`; pinned as
`test_mixes_restored_invalid_and_failed` below, now asserting each row
appears exactly once.
"""

from __future__ import annotations

import frappe

from jailbreak.jailbreak.overrides.version import Version, bulk_restore
from jailbreak.tests import JailbreakIntegrationTestCase
from jailbreak.tests.factories import make_note_with_version, set_capability


class TestRestoreDisabled(JailbreakIntegrationTestCase):
	"""Restore is disabled outright until it is rewritten (see the module
	docstring for why the old behaviour was a silent no-op). These replace
	the old S2 tests, which exercised code that can no longer be reached."""

	def test_restore_throws_even_with_the_capability_enabled(self):
		version = make_note_with_version(original="<p>original</p>", changed="<p>changed</p>")

		with self.capability_enabled("version_restore"):
			with self.assertRaises(frappe.ValidationError) as ctx:
				Version("Version", version.name).restore(alert=False)

		self.assertIn("Version restore is temporarily disabled", str(ctx.exception))
		self.assertFalse(frappe.db.get_value("Version", version.name, "restored"))
		self.assertEqual(frappe.db.get_value("Note", version.docname, "content"), "<p>changed</p>")

	def test_restore_throws_with_the_capability_disabled(self):
		version = make_note_with_version()
		set_capability("version_restore", 0)

		with self.assertRaises(frappe.ValidationError):
			Version("Version", version.name).restore(alert=False)


class TestBulkRestoreDisabled(JailbreakIntegrationTestCase):
	def test_bulk_restore_throws_instead_of_reporting_success(self):
		version = make_note_with_version()

		with self.capability_enabled("version_restore"):
			with self.assertRaises(frappe.ValidationError) as ctx:
				bulk_restore(frappe.as_json([version.name]))

		self.assertIn("Version restore is temporarily disabled", str(ctx.exception))
		self.assertFalse(frappe.db.get_value("Version", version.name, "restored"))
