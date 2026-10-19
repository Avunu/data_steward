# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""`after_install` copies the capability toggles from the old app's Jailbreak
Settings, and does nothing on a site that never had it."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from data_steward.install import CAPABILITY_FIELDS, NEW_SETTINGS, OLD_SETTINGS, copy_jailbreak_settings
from data_steward.tests import DataStewardIntegrationTestCase
from data_steward.tests.factories import make_settings


def _current() -> dict[str, int]:
	settings = frappe.get_single(NEW_SETTINGS)
	return {field: int(settings.get(field) or 0) for field in CAPABILITY_FIELDS.values()}


def _write_old_singles(values: dict[str, str]) -> None:
	singles = frappe.qb.DocType("Singles")
	frappe.qb.from_(singles).delete().where(singles.doctype == OLD_SETTINGS).run()
	for field, value in values.items():
		frappe.qb.into(singles).columns(singles.doctype, singles.field, singles.value).insert(
			OLD_SETTINGS, field, value
		).run()


class TestCopyJailbreakSettings(DataStewardIntegrationTestCase):
	def setUp(self) -> None:
		super().setUp()
		previous = _current()
		self.addCleanup(make_settings, **previous)

	def test_no_op_without_the_old_doctype(self):
		make_settings(**dict.fromkeys(CAPABILITY_FIELDS.values(), 0))

		with patch("data_steward.install._jailbreak_settings_exist", return_value=False):
			self.assertFalse(copy_jailbreak_settings())

		self.assertEqual(set(_current().values()), {0})

	def test_fresh_site_has_no_old_doctype(self):
		"""The test site never had the old app, so the real check says so."""
		from data_steward.install import _jailbreak_settings_exist

		self.assertFalse(_jailbreak_settings_exist())

	def test_copies_each_capability(self):
		make_settings(**dict.fromkeys(CAPABILITY_FIELDS.values(), 0))
		_write_old_singles(
			{
				"global_bulk_merge": "1",
				"item_convert_to_variant": "0",
				"payment_entry_set_clearance_date": "1",
				"journal_entry_remove_clearance": "1",
				# only the old app has it: ignored
				"version_restore": "1",
			}
		)

		with patch("data_steward.install._jailbreak_settings_exist", return_value=True):
			self.assertTrue(copy_jailbreak_settings())

		self.assertEqual(
			_current(),
			{
				"global_bulk_merge": 1,
				"item_convert_to_variant": 0,
				"payment_entry_set_clearance_date": 1,
				"journal_entry_manually_clear": 0,
				"journal_entry_remove_clearance": 1,
			},
		)

	def test_disabled_old_values_switch_new_ones_off(self):
		make_settings(**dict.fromkeys(CAPABILITY_FIELDS.values(), 1))
		_write_old_singles(dict.fromkeys(CAPABILITY_FIELDS, "0"))

		with patch("data_steward.install._jailbreak_settings_exist", return_value=True):
			copy_jailbreak_settings()

		self.assertEqual(set(_current().values()), {0})

	def test_after_install_runs_the_copy(self):
		from data_steward import install

		with patch.object(install, "copy_jailbreak_settings") as copy:
			install.after_install()

		copy.assert_called_once_with()
