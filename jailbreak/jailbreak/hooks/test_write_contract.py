# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""The contract the state-changing endpoints rely on now that they leave the
commit to the request:

- they accept POST only. A GET request never commits (`frappe.app` rolls it
  back), so a GET call would report success and save nothing; it would also
  skip the CSRF check;
- they never commit themselves;
- an error inside the write reaches the caller as itself, and the request's
  rollback leaves no partial write behind. A savepoint stands in for that
  rollback here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import patch

import frappe
from frappe.model.document import Document

from jailbreak.jailbreak.hooks import bulk_merge
from jailbreak.jailbreak.hooks.item import convert_to_variant
from jailbreak.jailbreak.hooks.journal_entry import (
	manually_clear_journal_entry,
	remove_clearance_date_journal_entry,
)
from jailbreak.jailbreak.hooks.payment_entry import set_clearance_date
from jailbreak.tests import JailbreakIntegrationTestCase
from jailbreak.tests.factories import (
	make_cleared_journal_entry,
	make_item,
	make_item_template,
	make_journal_entry,
	make_payment_entry,
)

if TYPE_CHECKING:
	from unittest.mock import MagicMock

SAVEPOINT = "jailbreak_write_contract"


def _commit_mock() -> MagicMock:
	# JailbreakIntegrationTestCase patches frappe.db.commit with a MagicMock.
	return cast("MagicMock", frappe.db.commit)


class TestPostOnly(JailbreakIntegrationTestCase):
	def test_state_changing_endpoints_accept_post_only(self):
		for fn in (
			convert_to_variant,
			manually_clear_journal_entry,
			remove_clearance_date_journal_entry,
			set_clearance_date,
			bulk_merge,
		):
			with self.subTest(endpoint=fn.__name__):
				self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[fn], ["POST"])


class TestErrorsReachTheCallerAndRollBack(JailbreakIntegrationTestCase):
	def _call_in_savepoint(self, fn: Any, *args: Any) -> BaseException:
		"""Call `fn`, expect it to raise, and roll back to before the call the
		way the request would."""
		frappe.db.savepoint(SAVEPOINT)
		_commit_mock().reset_mock()
		try:
			fn(*args)
		except Exception as exc:
			frappe.db.rollback(save_point=SAVEPOINT)
			_commit_mock().assert_not_called()
			return exc
		self.fail(f"{fn.__name__} did not raise")

	def test_convert_to_variant_validation_error_is_not_wrapped(self):
		"""No attribute values leaves the Item's attribute table empty, so
		`Item.validate` throws after `variant_of` has already been written."""
		item = make_item("_JB Test Convert Error Path")
		template = make_item_template()

		with self.capability_enabled("item_convert_to_variant"):
			exc = self._call_in_savepoint(convert_to_variant, item.name, template.name, {})

		self.assertIsInstance(exc, frappe.ValidationError)
		self.assertIn("Attribute table is mandatory", str(exc))
		self.assertNotIn("Error converting", str(exc))
		self.assertFalse(frappe.db.get_value("Item", item.name, "variant_of"))

	def test_journal_entry_error_after_the_write_rolls_it_back(self):
		je = make_cleared_journal_entry(clearance_date="2020-02-02")
		boom = frappe.ValidationError("comment failed")

		with (
			self.capability_enabled("journal_entry_manually_clear"),
			patch.object(Document, "add_comment", side_effect=boom),
		):
			exc = self._call_in_savepoint(manually_clear_journal_entry, je.name)

		self.assertIs(exc, boom)
		self.assertIsNone(frappe.db.get_value("Journal Entry", je.name, "clearance_date"))

	def test_remove_clearance_error_after_the_write_rolls_it_back(self):
		je = make_journal_entry()
		frappe.db.set_value("Journal Entry", je.name, "clearance_date", "2020-02-02")
		boom = frappe.ValidationError("comment failed")

		with (
			self.capability_enabled("journal_entry_remove_clearance"),
			patch.object(Document, "add_comment", side_effect=boom),
		):
			exc = self._call_in_savepoint(remove_clearance_date_journal_entry, je.name)

		self.assertIs(exc, boom)
		self.assertEqual(str(frappe.db.get_value("Journal Entry", je.name, "clearance_date")), "2020-02-02")

	def test_payment_entry_error_after_the_write_rolls_it_back(self):
		pe = make_payment_entry(reference_no="_JB-ERR-PE-1")
		boom = frappe.ValidationError("comment failed")

		with (
			self.capability_enabled("payment_entry_set_clearance_date"),
			patch.object(Document, "add_comment", side_effect=boom),
		):
			exc = self._call_in_savepoint(set_clearance_date, pe.name, "2021-06-15")

		self.assertIs(exc, boom)
		self.assertIsNone(frappe.db.get_value("Payment Entry", pe.name, "clearance_date"))


class TestEndpointsDoNotCommit(JailbreakIntegrationTestCase):
	def test_success_paths_leave_the_commit_to_the_request(self):
		item = make_item("_JB Test Convert No Commit")
		template = make_item_template()
		je = make_cleared_journal_entry(clearance_date="2020-02-02")
		pe = make_payment_entry(reference_no="_JB-NOCOMMIT-PE-1")

		with (
			self.capability_enabled("item_convert_to_variant"),
			self.capability_enabled("journal_entry_manually_clear"),
			self.capability_enabled("journal_entry_remove_clearance"),
			self.capability_enabled("payment_entry_set_clearance_date"),
		):
			_commit_mock().reset_mock()
			convert_to_variant(item.name, template.name, {"Colour": "Red"})
			manually_clear_journal_entry(je.name)
			remove_clearance_date_journal_entry(je.name)
			set_clearance_date(pe.name, "2021-06-15")
			_commit_mock().assert_not_called()
