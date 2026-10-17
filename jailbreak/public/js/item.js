// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

/* global jailbreak */

// Custom Script for Item DocType
frappe.ui.form.on("Item", {
	refresh: function (frm) {
		if (!frm.is_new()) {
			// Check if the item convert to variant capability is enabled
			jailbreak.check_capability("item_convert_to_variant").then((enabled) => {
				if (enabled) {
					frm.add_custom_button(
						__("Convert to Variant"),
						function () {
							show_variant_dialog(frm);
						},
						__("Actions"),
					);
				}
			});
		}
	},
});

function show_variant_dialog(frm) {
	// First dialog to select the template
	let template_dialog = new frappe.ui.Dialog({
		title: __("Select Template Item"),
		fields: [
			{
				label: __("Template Item"),
				fieldname: "template_item",
				fieldtype: "Link",
				options: "Item",
				filters: {
					has_variants: 1,
				},
				reqd: 1,
			},
		],
		primary_action_label: __("Next"),
		primary_action: function () {
			let template = template_dialog.get_value("template_item");
			if (template) {
				load_attributes_and_show_dialog(template);
				template_dialog.hide();
			}
		},
	});

	template_dialog.show();

	function load_attributes_and_show_dialog(template) {
		frappe.db.get_doc("Item", template).then((template_doc) => {
			let attributes = template_doc.attributes || [];
			if (!attributes.length) {
				frappe.msgprint(__("This template has no attributes."));
				return;
			}

			// Get all attribute data
			let promises = attributes.map((attr) => {
				return frappe.db.get_doc("Item Attribute", attr.attribute);
			});

			Promise.all(promises).then((attr_docs) => {
				// Build dialog fields
				let fields = [
					{
						fieldtype: "HTML",
						fieldname: "template_html",
						options: `<p class="text-muted">${__("Template")}: <strong>${
							template_doc.item_name || template
						}</strong></p>`,
					},
					{
						fieldtype: "Section Break",
						fieldname: "attribute_fields_section",
						label: __("Attribute Values"),
					},
				];

				// Add fields for each attribute
				attr_docs.forEach((attr_doc, i) => {
					if (i > 0 && i % 3 === 0) {
						fields.push({ fieldtype: "Section Break" });
					} else if (i > 0) {
						fields.push({ fieldtype: "Column Break" });
					}

					fields.push({
						label: __(attr_doc.attribute_name),
						fieldname: `attribute_${attr_doc.name}`,
						fieldtype: "Select",
						options: attr_doc.item_attribute_values.map((a) => a.attribute_value).join("\n"),
						reqd: 1,
					});
				});

				// Create the final dialog with all fields
				let attribute_dialog = new frappe.ui.Dialog({
					title: __("Convert to Variant"),
					fields: fields,
					primary_action_label: __("Convert"),
					primary_action: function () {
						let values = attribute_dialog.get_values();
						if (values) {
							// Extract attribute values
							let attribute_values = {};
							Object.keys(values).forEach((key) => {
								if (key.startsWith("attribute_")) {
									let attribute_name = key.replace("attribute_", "");
									attribute_values[attribute_name] = values[key];
								}
							});

							frappe.call({
								method: "jailbreak.jailbreak.hooks.item.convert_to_variant",
								args: {
									item: frm.doc.name,
									template: template,
									attribute_values: attribute_values,
								},
								callback: function (r) {
									if (!r.exc) {
										frappe.show_alert({
											message: __("Item converted to variant successfully"),
											indicator: "green",
										});
										frm.reload_doc();
									}
								},
							});
							attribute_dialog.hide();
						}
					},
				});

				attribute_dialog.show();
			});
		});
	}
}
