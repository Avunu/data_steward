// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

/* global data_steward */

// Set full-width default if not already set
if (!Object.prototype.hasOwnProperty.call(localStorage, "container_fullwidth")) {
	localStorage.container_fullwidth = "true";
	frappe.ui.toolbar.set_fullwidth_if_enabled();
}
