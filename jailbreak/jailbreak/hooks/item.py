from typing import TYPE_CHECKING, cast

import frappe
from frappe import _

from jailbreak import assert_capability
from jailbreak.jailbreak.doctype.jailbreak_settings.jailbreak_settings import require_roles

if TYPE_CHECKING:
	from erpnext.stock.doctype.item.item import Item


@frappe.whitelist()
def convert_to_variant(item: str, template: str, attribute_values: dict | str) -> bool:
	# Check if the item convert to variant capability is enabled
	assert_capability("item_convert_to_variant")
	require_roles("Item Manager", "System Manager")
	# The variant_of write below bypasses Item permissions, so check them first.
	frappe.has_permission("Item", "write", item, throw=True)

	try:
		# Parse attribute_values if it's a string
		if isinstance(attribute_values, str):
			import json

			attribute_values = json.loads(attribute_values)

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

			# Get the attribute value from the submitted values
			# The key in attribute_values is in format "attribute_NAME"
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
		frappe.db.commit()

		return True

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), _("Item to Variant Conversion Error"))
		frappe.throw(_("Error converting item to variant: {0}").format(str(e)))
		return False
