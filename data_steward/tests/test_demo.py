# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""The demo hook frappe-demo calls (`data_steward.demo.setup`)."""

import datetime

import frappe

from data_steward import demo
from data_steward.data_steward.doctype.data_steward_settings.data_steward_settings import check_capability
from data_steward.tests import DataStewardIntegrationTestCase
from data_steward.tests.factories import make_settings

CTX = {"today": datetime.date(2026, 1, 15), "seed": 1, "company": None, "erpnext_demo": False}


class TestDemo(DataStewardIntegrationTestCase):
	def setUp(self):
		# setup() switches every tool on; put the settings back so later tests start from theirs.
		before = {
			capability: frappe.db.get_single_value(demo.SETTINGS, capability)
			for capability in demo.CAPABILITIES
		}
		self.addCleanup(make_settings, **before)

	def test_setup_enables_every_tool(self):
		demo.setup(CTX)
		for capability in demo.CAPABILITIES:
			self.assertTrue(check_capability(capability), capability)

	def test_setup_creates_the_duplicates_and_the_loose_item(self):
		demo.setup(CTX)
		for name in demo.DUPLICATE_CUSTOMERS + demo.OTHER_CUSTOMERS:
			self.assertTrue(frappe.db.exists("Customer", name), name)
		self.assertEqual(frappe.db.get_value("Item", demo.TEMPLATE, "has_variants"), 1)
		self.assertFalse(frappe.db.get_value("Item", demo.LOOSE_ITEM, "variant_of"))
		description = frappe.db.get_value("Item", demo.LOOSE_ITEM, "description")
		assert isinstance(description, str)
		self.assertIn("2026", description)

	def test_setup_is_idempotent(self):
		demo.setup(CTX)
		demo.setup(CTX)
		self.assertEqual(frappe.db.count("Customer", {"name": ["in", demo.DUPLICATE_CUSTOMERS]}), 3)
		self.assertEqual(frappe.db.count("Item", {"name": ["in", [demo.TEMPLATE, demo.LOOSE_ITEM]]}), 2)
		self.assertEqual(frappe.db.count("Item Attribute", {"name": ["in", list(demo.ATTRIBUTES)]}), 2)
