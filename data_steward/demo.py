# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""Demo data for frappe-demo and the screenshots in docs/screenshots/.

Every tool is switched on in Data Steward Settings, and the site gets the kind
of data the tools exist to fix: three Customers that are one company entered
three times, and an Item that should have been a variant of a template.
"""

import frappe

SETTINGS = "Data Steward Settings"
CAPABILITIES = (
	"global_bulk_merge",
	"item_convert_to_variant",
	"payment_entry_set_clearance_date",
	"journal_entry_manually_clear",
	"journal_entry_remove_clearance",
)

# The same company, entered three times, among customers that are not duplicates.
DUPLICATE_CUSTOMERS = ("Harbor Supply Co.", "Harbor Supply Company", "Harbor Supply Co")
OTHER_CUSTOMERS = ("Northwind Traders", "Bluebird Bakery", "Granite Peak Outfitters")

# A template Item and a stand-alone Item that is really one of its variants.
ATTRIBUTES = {
	"Shirt Colour": ("Navy", "White", "Heather Grey"),
	"Shirt Size": ("Small", "Medium", "Large", "X-Large"),
}
TEMPLATE = "TSHIRT-CLASSIC"
LOOSE_ITEM = "TSHIRT-NAVY-LARGE"


def _leaf(doctype: str) -> str:
	"""The first non-group record of a tree DocType (Customer Group, Territory, Item Group)."""
	return str(
		frappe.db.get_value(doctype, {"is_group": 0}, "name", order_by="lft")
		or frappe.db.get_value(doctype, {}, "name", order_by="lft")
	)


def setup(ctx):
	"""Switch every tool on and create the demo records, once; `ctx["today"]` dates them."""
	settings = frappe.get_doc(SETTINGS)
	for capability in CAPABILITIES:
		settings.set(capability, 1)
	settings.save(ignore_permissions=True)

	customer_group = _leaf("Customer Group")
	territory = _leaf("Territory")
	for name in DUPLICATE_CUSTOMERS + OTHER_CUSTOMERS:
		if frappe.db.exists("Customer", name):
			continue
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": name,
				"customer_type": "Company",
				"customer_group": customer_group,
				"territory": territory,
			}
		).insert(ignore_permissions=True, set_name=name)

	for attribute, values in ATTRIBUTES.items():
		if frappe.db.exists("Item Attribute", attribute):
			continue
		frappe.get_doc(
			{
				"doctype": "Item Attribute",
				"attribute_name": attribute,
				"item_attribute_values": [
					{"attribute_value": value, "abbr": value[:3].upper()} for value in values
				],
			}
		).insert(ignore_permissions=True)

	item_group = _leaf("Item Group")
	if not frappe.db.exists("Item", TEMPLATE):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": TEMPLATE,
				"item_name": "Classic T-Shirt",
				"item_group": item_group,
				"stock_uom": "Nos",
				"has_variants": 1,
				"attributes": [{"attribute": attribute} for attribute in ATTRIBUTES],
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("Item", LOOSE_ITEM):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": LOOSE_ITEM,
				"item_name": "Classic T-Shirt, Navy, Large",
				"item_group": item_group,
				"stock_uom": "Nos",
				"description": f"Added by hand on {frappe.utils.formatdate(ctx['today'])}, before the template existed.",
			}
		).insert(ignore_permissions=True)
