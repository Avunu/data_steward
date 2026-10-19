# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

import json
from typing import TYPE_CHECKING, cast

import frappe
from frappe import _

from data_steward.api import assert_capability
from data_steward.data_steward.doctype.data_steward_settings.data_steward_settings import require_roles

if TYPE_CHECKING:
	from erpnext.stock.doctype.item.item import Item


@frappe.whitelist(methods=["POST"])
def convert_to_variant(item: str, template: str, attribute_values: dict | str) -> bool:
	"""Make `item` a variant of `template`, taking the template's attributes.

	Sets `variant_of` directly on purpose: it is `set_only_once`, so a normal
	save would refuse the change. No commit here: the request commits on
	success and rolls back on an error.
	"""
	# Check if the item convert to variant capability is enabled
	assert_capability("item_convert_to_variant")
	require_roles("Item Manager", "System Manager")
	# The variant_of write below bypasses Item permissions, so check them first.
	frappe.has_permission("Item", "write", item, throw=True)

	# Parse attribute_values if it's a string
	if isinstance(attribute_values, str):
		attribute_values = cast(dict, json.loads(attribute_values))

	# Update variant fields
	frappe.db.set_value("Item", item, "variant_of", template)

	# Get the source item and template
	item_doc: Item = cast("Item", frappe.get_doc("Item", item))
	template_doc: Item = cast("Item", frappe.get_doc("Item", template))

	# Clear existing attributes
	item_doc.attributes = []

	# Add all attributes from the template with their values
	for template_attribute in template_doc.attributes:
		attribute_name = template_attribute.attribute

		# Get the attribute value from the submitted values, keyed by attribute name
		attribute_value = attribute_values.get(attribute_name)

		if attribute_value:
			item_doc.append(
				"attributes",
				{"attribute": attribute_name, "attribute_value": attribute_value},
			)

	# Handle UOM conversion
	if item_doc.stock_uom != template_doc.stock_uom:
		old_stock_uom = item_doc.stock_uom
		item_doc.stock_uom = template_doc.stock_uom
		item_doc.sales_uom = old_stock_uom

	item_doc.save()
	item_doc.add_comment("Edit", _("Converted to a variant of {0}").format(template))
	return True
