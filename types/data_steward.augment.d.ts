// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

// Globals this app defines for its own desk scripts. frappe's globals are not
// declared here: they come from frappe-types.

declare global {
	/** A capability in Data Steward Settings: `capability_name` in data_steward_settings.py. */
	type DataStewardCapability =
		| "global_bulk_merge"
		| "item_convert_to_variant"
		| "file_merge"
		| "payment_entry_set_clearance_date"
		| "journal_entry_manually_clear"
		| "journal_entry_remove_clearance";

	/** `window.data_steward`, set up by `public/js/data_steward.js` in the desk bundle. */
	interface DataStewardDesk {
		/** Whether a capability is enabled, for UI decisions; false when the call fails. */
		check_capability(capability: DataStewardCapability): Promise<boolean>;
	}

	/** One entry of `merge_files`'s answer: `FileMergeResult` in `hooks/file.py`. */
	interface DataStewardFileMergeResult {
		file: string;
		merged: boolean;
		references: number;
		message: string;
	}

	/** `frappe.ui.file_merge`, set up by `public/js/file_merge.js` in the desk bundle. */
	interface DataStewardFileMerge {
		/** Confirms, merges `files` into `keep` and shows the log; null when the user does not go ahead. */
		confirm_and_merge(
			keep: string,
			keep_label: string,
			files: string[],
		): Promise<DataStewardFileMergeResult[] | null>;
		/** Shows one line per merged or failed file. */
		show_log(keep_label: string, results: DataStewardFileMergeResult[]): void;
		/** Whether the user has the role the server requires: System Manager, or Administrator. */
		may_merge(): boolean;
		/** Adds Merge Files to the File list's Actions menu, once per view, for a System Manager when the tool is on. */
		add_list_action(listview: frappe.views.ListView | frappe.views.ReportView): void;
		/** The dialog behind the list's Merge Files. */
		merge_checked_files(listview: frappe.views.ListView | frappe.views.ReportView): void;
		/** The dialog behind the File form's Merge into... */
		merge_into(frm: frappe.ui.form.Form<"File">): void;
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
		// app-owned: set by file_merge.js in the desk bundle
		file_merge: DataStewardFileMerge;
	}

	interface ListView<TColumn> {
		// app-owned: file_merge.js sets it once it has added Merge Files to the view
		data_steward_file_merge?: boolean;
	}
}
