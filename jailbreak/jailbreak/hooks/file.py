# Copyright (c) 2025, Avunu LLC and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _
from frappe.model.rename_doc import rename_doc

from jailbreak import assert_capability


@frappe.whitelist()
def merge_files(source_file: str, target_file: str) -> dict:
	"""
	Merge source_file into target_file by using rename_doc with merge=True.
	This leverages Frappe's built-in merge functionality which handles reference updates automatically.

	:param source_file: Name of the file to merge (will be deleted)
	:param target_file: Name of the file to merge into (will be kept)
	:return: Dictionary with success status and message
	"""
	# Check if file merge capability is enabled
	assert_capability("file_merge")

	# Validate that both files exist
	if not frappe.db.exists("File", source_file):
		frappe.throw(_("Source file {0} does not exist").format(source_file))

	if not frappe.db.exists("File", target_file):
		frappe.throw(_("Target file {0} does not exist").format(target_file))

	# Prevent merging a file into itself
	if source_file == target_file:
		frappe.throw(_("Cannot merge a file into itself"))

	# Get the source file document to access filesystem path before merging
	source_file_doc = frappe.get_doc("File", source_file)
	file_path = source_file_doc.get_full_path()

	# Use rename_doc with merge=True and force=True to merge the files
	# This handles all reference updates automatically
	rename_doc(
		doctype="File",
		old=source_file,
		new=target_file,
		force=True,
		merge=True,
		ignore_permissions=True,
		show_alert=False,
		rebuild_search=False,  # We'll rebuild once at the end
	)

	# Delete the physical file from filesystem if it exists
	if file_path and os.path.exists(file_path):
		try:
			os.remove(file_path)
		except OSError as e:
			frappe.log_error(
				f"Failed to delete file {file_path}: {str(e)}. Database merge succeeded but physical file was not removed.",
				"File Merge - Filesystem Cleanup",
			)

	return {
		"success": True,
		"message": _("File {0} merged into {1} successfully.").format(source_file, target_file),
	}


@frappe.whitelist()
def batch_merge_files(files_to_merge: str | list, target_file: str) -> dict:
	"""
	Merge multiple files into a target file.

	:param files_to_merge: List of file names to merge (will be deleted)
	:param target_file: Name of the file to merge into (will be kept)
	:return: Dictionary with success status and message
	"""
	import json

	# Check if file merge capability is enabled
	assert_capability("file_merge")

	# Parse files_to_merge if it's a JSON string
	if isinstance(files_to_merge, str):
		files_to_merge = json.loads(files_to_merge)

	if not files_to_merge:
		frappe.throw(_("No files selected to merge"))

	merged_count = 0
	failed_files = []

	for source_file in files_to_merge:
		try:
			result = merge_files(source_file, target_file)
			if result.get("success"):
				merged_count += 1
		except Exception as e:
			failed_files.append({"file": source_file, "error": str(e)})
			frappe.log_error(f"Failed to merge {source_file} into {target_file}: {str(e)}", "Batch File Merge Error")

	message = _("{0} file(s) merged into {1} successfully.").format(merged_count, target_file)

	if failed_files:
		message += " " + _("{0} file(s) failed to merge.").format(len(failed_files))

	return {
		"success": True,
		"message": message,
		"merged_count": merged_count,
		"failed_files": failed_files,
	}
