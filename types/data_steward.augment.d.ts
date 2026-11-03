// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

// Globals this app defines for its own desk scripts. frappe's globals are not
// declared here: they come from frappe-types.

import type { DisplayStatus, DocField, FrappeDoc, Permission } from "frappe-types";

declare global {
	/** A capability in Data Steward Settings: `capability_name` in data_steward_settings.py. */
	type DataStewardCapability =
		| "global_bulk_merge"
		| "item_convert_to_variant"
		| "payment_entry_set_clearance_date"
		| "journal_entry_manually_clear"
		| "journal_entry_remove_clearance";

	/** `window.data_steward`, set up by `public/js/data_steward.js` in the desk bundle. */
	interface DataStewardDesk {
		/** Whether a capability is enabled, for UI decisions; false when the call fails. */
		check_capability(capability: DataStewardCapability): Promise<boolean>;
	}

	// app-owned: set by data_steward.js, which the desk bundle loads before every doctype script
	var data_steward: DataStewardDesk;
}

/** `frappe.ui.merge_records`, set up by `public/js/merge_records.js` in the desk bundle. */
export interface DataStewardMergeRecords {
	/** Opens the merge dialog for the rows checked in `listview`. */
	merge_selected_records(listview: frappe.views.ListView): void;
}

declare module "frappe-types" {
	interface FrappeUiNamespace {
		// app-owned: set by merge_records.js in the desk bundle
		merge_records: DataStewardMergeRecords;
	}

	// Frappe's own, which frappe-types does not declare yet; only what side_panel.js calls.
	interface Frappe {
		/** frappe/public/js/frappe/model/perm.js */
		perm: {
			/** perm.js:232-308 — "Write", "Read" or "None" for `df` on `doc`, given `perm` by permlevel. */
			get_field_display_status(
				df: DocField,
				doc: FrappeDoc,
				perm: Permission[],
				explain?: boolean,
			): DisplayStatus;
		};
		/** frappe/public/js/frappe/model/workflow.js */
		workflow: {
			/** workflow.js:22-27 — the workflow's state field, or null when the doctype has no workflow. */
			get_state_fieldname(doctype: string): string | null;
			/** workflow.js:28-41 — the first state with this docstatus. */
			get_default_state(doctype: string, docstatus: number | undefined): string | null;
			/** workflow.js:43-49 — the roles that may edit a document in `state`. */
			get_document_state_roles(doctype: string, state: string): string[];
		};
	}
}
