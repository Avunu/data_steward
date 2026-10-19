# Copyright (c) 2026, Avunu LLC and Contributors
# See license.txt

"""S1 coverage for the two functions every other whitelisted function in this
app calls first: `assert_capability`/`check_capability`. Also covers the
identical wrappers in `data_steward/api.py`, since that is the path every JS
caller actually goes through (`data_steward.api.check_capability`,
`data_steward.api.assert_capability`)."""

from __future__ import annotations

from contextlib import AbstractContextManager
from unittest.mock import patch

import frappe
from frappe.tests.classes.context_managers import set_user

from data_steward.data_steward.doctype.data_steward_settings.data_steward_settings import (
	assert_capability,
	check_capability,
	require_roles,
)
from data_steward.tests import DataStewardIntegrationTestCase
from data_steward.tests.factories import make_user, set_capability


class TestCheckCapability(DataStewardIntegrationTestCase):
	def test_disabled_capability_is_false(self):
		set_capability("global_bulk_merge", 0)
		self.assertFalse(check_capability("global_bulk_merge"))

	def test_enabled_capability_is_true(self):
		with self.capability_enabled("global_bulk_merge"):
			self.assertTrue(check_capability("global_bulk_merge"))

	def test_unknown_capability_is_false_not_an_error(self):
		self.assertFalse(check_capability("not_a_real_capability"))


class TestAssertCapability(DataStewardIntegrationTestCase):
	def test_disabled_capability_raises_permission_error(self):
		set_capability("journal_entry_remove_clearance", 0)
		with self.assertRaises(frappe.PermissionError):
			assert_capability("journal_entry_remove_clearance")

	def test_enabled_capability_does_not_raise(self):
		with self.capability_enabled("journal_entry_remove_clearance"):
			self.assertIsNone(assert_capability("journal_entry_remove_clearance"))

	def test_unknown_capability_raises_validation_error(self):
		with self.assertRaises(frappe.ValidationError):
			assert_capability("not_a_real_capability")


class TestMissingSettings(DataStewardIntegrationTestCase):
	"""A Single always loads, but if `Data Steward Settings` cannot be read the
	check fails closed: `check_capability` is False and `assert_capability`
	raises DoesNotExistError."""

	def _missing(self) -> AbstractContextManager[object]:
		return patch.object(frappe, "get_cached_doc", side_effect=frappe.DoesNotExistError)

	def test_check_capability_is_false(self):
		with self._missing():
			self.assertFalse(check_capability("global_bulk_merge"))

	def test_assert_capability_raises_does_not_exist(self):
		with self._missing(), self.assertRaises(frappe.DoesNotExistError):
			assert_capability("global_bulk_merge")


class TestTopLevelWrappers(DataStewardIntegrationTestCase):
	"""`data_steward/api.py`'s `assert_capability`/`check_capability` are
	the actual whitelisted entry points every JS caller reaches
	(`data_steward.api.check_capability` in `frappe.call`) - they just delegate to
	the module above, but that delegation is worth pinning on its own."""

	def test_wrapper_check_capability_delegates(self):
		from data_steward import api

		with self.capability_enabled("journal_entry_remove_clearance"):
			self.assertTrue(api.check_capability("journal_entry_remove_clearance"))

	def test_wrapper_assert_capability_delegates(self):
		from data_steward import api

		set_capability("journal_entry_remove_clearance", 0)
		with self.assertRaises(frappe.PermissionError):
			api.assert_capability("journal_entry_remove_clearance")


class TestRequireRoles(DataStewardIntegrationTestCase):
	def test_user_without_any_listed_role_raises_permission_error(self):
		user = make_user("ds_test_roles_none@example.com")
		with set_user(user.name), self.assertRaises(frappe.PermissionError):
			require_roles("Accounts Manager", "System Manager")

	def test_any_one_listed_role_is_enough(self):
		user = make_user("ds_test_roles_sysman@example.com", "System Manager")
		with set_user(user.name):
			self.assertIsNone(require_roles("Accounts Manager", "System Manager"))

	def test_administrator_always_passes(self):
		with set_user("Administrator"):
			self.assertIsNone(require_roles("Accounts Manager"))
