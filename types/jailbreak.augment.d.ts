// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

// Globals this app defines for its own desk scripts. frappe's globals are not
// declared here: they come from frappe-types.

declare global {
	/** A capability in Jailbreak Settings: `capability_name` in jailbreak_settings.py. */
	type JailbreakCapability =
		| "global_bulk_merge"
		| "item_convert_to_variant"
		| "version_restore"
		| "payment_entry_set_clearance_date"
		| "journal_entry_manually_clear"
		| "journal_entry_remove_clearance";

	/** `window.jailbreak`, set up by `public/js/jailbreak.js` in the desk bundle. */
	interface JailbreakDesk {
		/** Whether a capability is enabled, for UI decisions; false when the call fails. */
		check_capability(capability: JailbreakCapability): Promise<boolean>;
	}

	// app-owned: set by jailbreak.js, which the desk bundle loads before every doctype script
	var jailbreak: JailbreakDesk;
}

/** `frappe.ui.merge_records`, set up by `public/js/merge_records.js` in the desk bundle. */
export interface JailbreakMergeRecords {
	/** Opens the merge dialog for the rows checked in `listview`. */
	merge_selected_records(listview: frappe.views.ListView): void;
}

declare module "frappe-types" {
	interface FrappeUiNamespace {
		// app-owned: set by merge_records.js in the desk bundle
		merge_records: JailbreakMergeRecords;
	}
}
