// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

import type { ShotSpec } from "./shots.d.ts";

// The demo records from data_steward/demo.py.
const DUPLICATES = ["Harbor Supply Co.", "Harbor Supply Company", "Harbor Supply Co"];
const LOOSE_ITEM = "TSHIRT-NAVY-LARGE";
const TEMPLATE = "TSHIRT-CLASSIC";

// Tick the three duplicate Customers, then open the dialog the "Merge Selected" action opens.
const SELECT_DUPLICATES = `
	for (const name of ${JSON.stringify(DUPLICATES)}) {
		const box = document.querySelector('.list-row-checkbox[data-name="' + CSS.escape(name) + '"]');
		if (box && !box.checked) box.click();
	}
`;

export default {
	demo: { date: "2026-01-15", seed: 1 },
	shots: [
		{
			name: "merge-records",
			route: "/app/customer?customer_name=%5B%22like%22%2C%22%25Harbor%25%22%5D",
			alt: "Three duplicate Customers ticked in the list view, and the Merge Records dialog asking which one to keep",
			waitForFn:
				"window.cur_list && cur_list.doctype === 'Customer' && cur_list.data && cur_list.data.length === 3",
			actions: [
				{ eval: SELECT_DUPLICATES },
				{ wait: 300 },
				{ eval: "frappe.ui.merge_records.merge_selected_records(cur_list);" },
				{ waitFor: ".modal.show [data-fieldname='merge_into'] select" },
				{ eval: `cur_dialog.set_value("merge_into", ${JSON.stringify(DUPLICATES[0])});` },
				{ wait: 500 },
			],
			mask: [".frappe-timestamp"],
			readme: "hero",
			featured: true,
		},
		{
			name: "convert-to-variant",
			route: `/app/item/${LOOSE_ITEM}`,
			alt: "An existing Item being converted into a variant of the Classic T-Shirt template, with its colour and size picked",
			waitForFn: `window.cur_frm && cur_frm.doc && cur_frm.doc.name === ${JSON.stringify(LOOSE_ITEM)} && !!cur_frm.custom_buttons["Convert to Variant"]`,
			actions: [
				// The button is added once the capability check returns; clicking it is what the
				// Actions menu entry does.
				{ eval: 'cur_frm.custom_buttons["Convert to Variant"].trigger("click"); null;' },
				{ waitFor: ".modal.show [data-fieldname='template_item'] input" },
				// A Link value is validated against the server before get_value() returns it.
				{ eval: `cur_dialog.set_value("template_item", ${JSON.stringify(TEMPLATE)});` },
				{ wait: 2000 },
				// Pressed from script: a click at the button's position can land on the link field's
				// suggestion list instead.
				{ eval: "cur_dialog.get_primary_btn().trigger('click'); null;" },
				{ waitFor: ".modal.show [data-fieldname='attribute_Shirt Colour'] select" },
				{
					eval: 'cur_dialog.set_values({ "attribute_Shirt Colour": "Navy", "attribute_Shirt Size": "Large" });',
				},
				{ wait: 500 },
			],
			mask: [".frappe-timestamp"],
			readme: "feature",
			featured: true,
		},
		{
			name: "settings",
			route: "/app/data-steward-settings",
			alt: "Data Steward Settings, with one check box for each tool",
			waitFor: "[data-fieldname='global_bulk_merge'] input",
			// The comment box and the change log under the form are not part of the settings.
			hide: [".form-footer"],
			// Masks paint hidden elements too, so only the sidebar's timestamp.
			mask: [".form-sidebar .frappe-timestamp"],
			readme: "feature",
		},
	],
} satisfies ShotSpec;
