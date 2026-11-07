// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

/* global data_steward */

/** @param {string} text */
const escape = (text) => frappe.utils.escape_html(text);

/**
 * How a File reads in the dialogs: its file name, then its ID. Plain text: a
 * file name may hold `<` or `"`, so escape it wherever it goes into HTML.
 * @param {{name: string, file_name?: unknown}} file
 */
const file_label = (file) => (file.file_name ? `${file.file_name} (${file.name})` : file.name);

frappe.provide("frappe.ui.file_merge");

frappe.ui.file_merge = {
	/**
	 * Ask once more, then merge `files` into `keep` and show one line per file.
	 * @param {string} keep
	 * @param {string} keep_label
	 * @param {string[]} files
	 * @returns {Promise<DataStewardFileMergeResult[] | null>} null when the user does not go ahead
	 */
	confirm_and_merge(keep, keep_label, files) {
		return new Promise((resolve) => {
			let merging = false;
			const message = [
				`<p>${escape(__("Merge {0} file(s) into {1}?", [String(files.length), keep_label]))}</p>`,
				`<p>${escape(
					__(
						"Every Attach field, text and link that refers to a merged file will refer to the kept file instead. A merged file that is attached to a document stays on it as an attachment of the kept file; every other merged file is deleted, and its content is removed once no file uses it.",
					),
				)}</p>`,
				`<p><strong>${escape(__("This cannot be undone."))}</strong></p>`,
			].join("");
			const dialog = frappe.warn(
				__("Merge Files"),
				message,
				() => {
					merging = true;
					frappe
						.call({
							method: "data_steward.data_steward.hooks.file.merge_files",
							args: { keep: keep, files: files },
							freeze: true,
							freeze_message: __("Merging files..."),
						})
						.then((r) => {
							const results = /** @type {DataStewardFileMergeResult[]} */ (r.message || []);
							frappe.ui.file_merge.show_log(keep_label, results);
							resolve(results);
						})
						.catch(() => resolve(null));
				},
				__("Merge"),
			);
			dialog.onhide = () => {
				if (!merging) {
					resolve(null);
				}
			};
		});
	},

	/**
	 * @param {string} keep_label
	 * @param {DataStewardFileMergeResult[]} results
	 */
	show_log(keep_label, results) {
		const lines = results.map((result) =>
			result.merged
				? escape(
						__("Merged {0} into {1}: {2} reference(s) changed. {3}", [
							result.file,
							keep_label,
							String(result.references),
							result.message,
						]),
					)
				: `<span class="text-danger">${escape(__("Failed {0}: {1}", [result.file, result.message]))}</span>`,
		);
		frappe.msgprint({ title: __("File Merge Log"), message: lines.join("<br>") });
	},

	/**
	 * Add Merge Files to the Actions menu of the File list (Frappe's File
	 * Manager view, or its Report view), once per view.
	 * @param {frappe.views.ListView} listview
	 */
	add_list_action(listview) {
		const view = /** @type {frappe.views.ListView & {data_steward_file_merge?: boolean}} */ (listview);
		if (view.data_steward_file_merge) {
			return;
		}
		view.data_steward_file_merge = true;
		data_steward.check_capability("file_merge").then((enabled) => {
			if (enabled) {
				view.page.add_actions_menu_item(__("Merge Files"), () =>
					frappe.ui.file_merge.merge_checked_files(view),
				);
			}
		});
	},

	/**
	 * The list's Merge Files: pick the file to keep among the ticked ones.
	 * @param {frappe.views.ListView} listview
	 */
	merge_checked_files(listview) {
		const checked = listview.get_checked_items();
		if (checked.some((doc) => doc.is_folder)) {
			frappe.throw(__("Only files can be merged. Untick the folders."));
		}
		if (checked.length < 2) {
			frappe.throw(__("Please select at least two files to merge."));
		}

		const dialog = new frappe.ui.Dialog({
			title: __("Merge Files"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "warning",
					options: `<div class="alert alert-warning">${escape(
						__(
							"The other ticked files are merged into the file you keep. References to them change to the kept file, and the merged files are removed. This cannot be undone.",
						),
					)}</div>`,
				},
				{
					label: __("File to Keep"),
					fieldname: "keep",
					fieldtype: "Select",
					// Frappe writes a Select option's label as HTML
					options: checked.map((doc) => ({ label: escape(file_label(doc)), value: doc.name })),
					reqd: 1,
				},
			],
			primary_action_label: __("Merge"),
			primary_action: (values) => {
				const keep = /** @type {string} */ (values.keep);
				const kept = checked.find((doc) => doc.name === keep);
				if (!kept) {
					return;
				}
				const files = checked.filter((doc) => doc.name !== keep).map((doc) => doc.name);
				dialog.hide();
				frappe.ui.file_merge.confirm_and_merge(keep, file_label(kept), files).then((results) => {
					if (results) {
						listview.clear_checked_items();
						listview.refresh();
					}
				});
			},
		});
		dialog.show();
	},

	/**
	 * The form's Merge into...: merge this file into another one.
	 * @param {frappe.ui.form.Form<"File">} frm
	 */
	merge_into(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("Merge into..."),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "warning",
					options: `<div class="alert alert-warning">${escape(
						__("References to {0} change to the file you pick, and {0} is removed. This cannot be undone.", [
							file_label(frm.doc),
						]),
					)}</div>`,
				},
				{
					label: __("File to Keep"),
					fieldname: "keep",
					fieldtype: "Link",
					options: "File",
					reqd: 1,
					get_query: () => ({
						filters: {
							name: ["!=", frm.doc.name],
							is_folder: 0,
							is_private: frm.doc.is_private ? 1 : 0,
						},
					}),
				},
			],
			primary_action_label: __("Merge"),
			primary_action: (values) => {
				const keep = /** @type {string} */ (values.keep);
				dialog.hide();
				frappe.ui.file_merge.confirm_and_merge(keep, keep, [frm.doc.name]).then((results) => {
					if (results && results.some((result) => result.merged)) {
						frappe.set_route("Form", "File", keep);
					}
				});
			},
		});
		dialog.show();
	},
};
