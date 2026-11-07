---
title: How it works
description: How Data Steward gates each tool, and what each endpoint does on the server, from the capability check to the comment it leaves.
nav_title: How it works
order: 10
updated: 2026-11-07
---

Data Steward is one module, Data Steward, with one DocType, a desk bundle, four form scripts, a list script and eight endpoints, one of which replaces Frappe's side panel preview. It has no `doc_events`, no scheduled jobs, no server-side class overrides and no patches. Everything it changes, it changes when a user clicks a button.

## The capability gate

**Data Steward Settings** is a Single with one Check field per tool, all `0` by default. Two functions in `data_steward_settings.py` read it through `frappe.get_cached_doc`:

- `check_capability(capability)` returns `True` or `False` and never raises. The desk calls it through `data_steward.api.check_capability` before it adds a button; `window.data_steward.check_capability` in `public/js/data_steward.js` wraps the call in a promise that resolves `false` on any error.
- `assert_capability(capability)` raises `frappe.PermissionError` ("The {0} capability is not enabled.") when the tool is off, and `frappe.ValidationError` for a name it does not know. Every endpoint calls it first.

The second check is the role. `require_roles(*roles)` calls `frappe.only_for(roles, message=True)`, which lets the Administrator through and raises a permission error for a user with none of the roles. The third is the document permission, which each endpoint checks in its own way (below).

A tool being on says the tool is available on the site; the role and the permission say who may use it. The buttons only reflect the first: they are not hidden from users without the role.

## Bulk merge

`public/js/merge_records.js` replaces `frappe.views.ListView` with a subclass whose `setup_page` adds **Merge Selected** to the **Actions** menu, once per list view, when the DocType's meta has `allow_rename` and the tool is on. The desk bundle loads after Frappe's, so the base class is defined by then.

The dialog sends the DocType and one row per record to merge, `[<OLD_NAME>, <KEPT_NAME>, "true"]`, to `data_steward.data_steward.hooks.bulk_merge` (POST). After the capability and the System Manager check, it calls Frappe's `frappe.model.rename_doc.bulk_rename`. For each row that calls `rename_doc(..., merge=True)`, which checks write permission on both records and `allow_rename`, updates Link and Dynamic Link fields, moves attachments and versions, comments "merged … into …" on the kept record and deletes the old one (checking delete permission). `bulk_rename` commits after each successful row, rolls back a failed one, and returns one log line per row, which the desk shows in the **Merge Log** dialog. It refuses more than 500 rows.

## File merge

`public/js/file_list.js` is the File list script (`doctype_list_js`). Frappe's File list is the File Manager, a `FileView` that skips `onload`, so the script wraps `frappe.listview_settings.File.refresh`, which every list view calls after loading its rows, and asks `frappe.ui.file_merge.add_list_action` to add **Merge Files** to the **Actions** menu once per view when the tool is on. `public/js/file.js` adds **Actions → Merge into...** to a saved File that is not a folder. Both dialogs, the warning and the **File Merge Log** are in `public/js/file_merge.js`, in the desk bundle.

`data_steward.data_steward.hooks.file.merge_files` (POST) checks the capability and the System Manager role, takes at most 100 file names, and loads the kept File: it must be a file with a URL, the user needs write permission on it, and its content must exist (`exists_on_disk`, or `head_object` in cloud_storage's bucket). It then collects every Attach, Attach Image, Text Editor, HTML Editor, Markdown Editor, Long Text and Code field of every DocType with a table or a Single, from DocField, Custom Field and fieldtype Property Setters, skipping virtual DocTypes and fields, File, Version and Deleted Document, and keeps the ones that hold any of the URLs at all: one query per field for the whole run.

Each merged File then runs in its own savepoint, so a failure rolls back that file only and comes back as a log line:

1. **Checks.** Not the kept file, exists, not a folder, the same `is_private`, the same storage (`file_storage.storage_of`: on the site, cloud_storage's bucket, an external address), and delete permission.
2. **URLs.** `build_url_rewrite` lists each spelling of the merged URL (as stored, percent-encoded two ways, HTML-escaped, a cloud_storage key encoded whole; relative and with `get_url()`; with a private file's `?fid=<name>`) and one regular expression with boundaries on both sides, so `/files/a.png` never matches inside `/files/a.png.bak`. Attach fields are compared whole; text fields are read with `LIKE`, replaced in Python and written back with `frappe.db.bulk_update`, without `modified`; Singles go through `tabSingles`.
3. **Attachments.** Without cloud_storage, a merged File attached to an existing document that does not already have the kept file keeps its row and takes the kept file's `file_name`, `file_url`, `content_hash`, `file_size`, `file_type` and `thumbnail_url`, the attachment copy `File.create_attachment_copy` would make. With cloud_storage, see below. Other File rows with the merged file's `file_url` (or `s3_key`) take the kept file's content too.
4. **Delete.** Otherwise `update_link_field_values` and `rename_dynamic_links`, Frappe's rename helpers, move Link fields, comments, shares and versions to the kept File, and the merged row is deleted with `frappe.delete_doc` after its `file_url`, `content_hash`, `thumbnail_url`, `attached_to_*` (and `s3_key`, `sharing_link`) are cleared in the database. Frappe's `on_trash` deletes the content when no other row has the same hash, and cloud_storage's `delete_file_data_content` hook deletes whatever `file_url` names, so with nothing left to name, neither touches any content.
5. **Audit.** A comment on the kept File names the merged file, its URL and the number of references changed, plus what happened to its attachments and sharing link.

After the request commits, `file_storage.remove_leftover` (an `after_commit` callback) removes the merged file's content only when no File row uses it any more: a local `file_url` or `thumbnail_url` that no row's `file_url` or `thumbnail_url` holds, through Frappe's `File.delete_file_from_filesystem`, and only for a URL directly under `/files/` or `/private/files/`, because Frappe's `delete_file` takes the last path segment and would remove a file of the same name at the top. A cloud_storage key is deleted with the app's own client (`get_cloud_storage_client().delete_object`) when no row has it as `s3_key` or in its retrieve URL. An error there is logged and does not undo the merge.

### cloud_storage

`file_storage.has_cloud_storage()` is true when the app is installed and File has its `file_association` field; `cloud_storage_on()` when `cloud_storage_settings` is set without `use_local`. Nothing is imported from the app. When it is installed, the desk lists a document's attachments from `File Association` rows (the app replaces `frappe.desk.form.load.get_attachments`), so a merge moves the merged File's rows to the kept File (`_reparent_association`), drops a row for a document the kept File already has, adds one for a merged File's own `attached_to_*` that has none, and sets the kept File's `attached_to_*` to the first document when it had none. The merged row is then always deleted. Its `sharing_link` moves to the kept File when that has none; otherwise references to its `/api/method/share?key=` URL are rewritten to the kept File's. Its File Version rows are deleted with it.

## Convert to Variant

`public/js/item.js` adds the button on a saved Item and builds two dialogs: the template (a Link to Item filtered on `has_variants`) and one required Select per template attribute, filled from the Item Attribute's `item_attribute_values`.

`data_steward.data_steward.hooks.item.convert_to_variant` (POST) checks the capability, the Item Manager or System Manager role and write permission on the Item. It then:

1. writes `variant_of` with `frappe.db.set_value`, because the field is `set_only_once` and a normal save would refuse it;
2. replaces the Item's `attributes` with one row per template attribute that has a submitted value;
3. when the stock UOMs differ, sets the Item's `stock_uom` to the template's and its `sales_uom` to the old one;
4. saves the Item, so ERPNext's Item validation runs (including `validate_variant`, which refuses a template without `has_variants`);
5. comments "Converted to a variant of …" on the Item.

ERPNext's check for an existing variant with the same attributes, `validate_variant_attributes`, only runs for a new Item, so it does not run here.

## Clearance dates

`public/js/payment_entry.js` and `public/js/journal_entry.js` add their buttons only when `docstatus` is 1. The endpoints check it again.

- `hooks.payment_entry.set_clearance_date` (POST) checks the capability, the Accounts Manager or System Manager role, write permission and `docstatus == 1`, then the cheque date, then writes `clearance_date` with `frappe.db.set_value`.
- `hooks.journal_entry.manually_clear_journal_entry` (POST) does the same checks, then looks up the `date` of a Bank Transaction whose `Bank Transaction Payments` child rows have `payment_document = "Journal Entry"` and `payment_entry` equal to the entry. Pinning `payment_document` matters: `payment_entry` is a Dynamic Link, and a Payment Entry with the same name would match otherwise. With no match it returns "No matching bank transaction found." and writes nothing.
- `hooks.journal_entry.remove_clearance_date_journal_entry` (POST) writes `None`.

`hooks/clearance.py` holds the cheque-date rule, taken from ERPNext's `BankClearance.update_clearance_date`: when both dates are set, a clearance date before the cheque date (`reference_date` on Payment Entry, `cheque_date` on Journal Entry) raises "Clearance date {0} must be after cheque date {1}." with the title **Invalid Clearance Date**. A date equal to the cheque date passes, and removing a date is never checked. Each endpoint comments "Clearance Date changed from {0} to {1}" on the entry.

## Transactions

The endpoints never call `frappe.db.commit`. A POST request is committed by Frappe when the method returns and rolled back when it raises, so an error after the write, such as an ERPNext validation on the Item save, leaves nothing behind. Accepting POST only matters for that: Frappe rolls a GET request back, so a GET call would report success and save nothing, and it would skip the CSRF check. `bulk_rename` is the exception, committing each merged row itself.

## Install

`after_install` (`data_steward.install.after_install`) calls `copy_jailbreak_settings`. When the DocType **Jailbreak Settings** exists, it reads its values with `frappe.db.get_singles_dict`, without loading the other app's controller, and copies the five fields listed in `CAPABILITY_FIELDS` to Data Steward Settings. On any other site it does nothing.

## Side panel

Frappe's side panel (`frappe/public/js/frappe/ui/side_panel.js`, Frappe 16.50+) previews a document in a frm-less `frappe.ui.form.Layout`, the construction every Dialog uses, and forces each control's `get_status` to `"Read"`. `public/js/side_panel.js` turns that into an editing surface without forking the panel.

**Patching a lazy class.** The panel lives in `side_panel.bundle.js`, which Frappe loads on the first Link cell click. The desk bundle defines `frappe.ui.SidePanel` as an accessor property whose setter patches the class's prototype the moment that bundle assigns it, before the singleton is built, then turns the property back into a plain value. The patch wraps `make_buttons`, `open`, `back` and `close`, and replaces `render_doc`. A renderer that wraps the panel further, such as a doctype-specific view, keeps working: the guards only act on an editor that is on screen.

**Editing.** `render_doc` builds one `Layout` per doctype, as core does, and points it at a `structuredClone` of the preview's document, so the cached preview stays as loaded for Back and a revisit. Each control's `get_status` calls `frappe.perm.get_field_display_status`, the form's own rule (permlevel, docstatus, allow on submit, read only, set only once), with a permission array built from the preview: `permlevels` (readable) from Frappe, `write_permlevels` from Data Steward, emptied when the workflow state's `allow_edit` roles exclude the user (`frappe.workflow.is_read_only` reads `locals`, which the copy is not in). Tables and Buttons stay `"Read"`; empty read-only fields and a named document's `naming_series` are hidden, as on the form. Frm-less, a `Layout` skips `mandatory_depends_on` and `read_only_depends_on`, Link has no target for its fetched values, and Dynamic Link looks for its doctype in `locals`; the editor gives the layout a `set_dependant_property` and a `set_value`, and the Dynamic Link a `get_options`, that read the copy.

**Dirty state.** Each control's `set_model_value` is wrapped to note the fieldname and refresh dependencies. `get_changes()` compares those fields with the loaded document (a cleared field matches a null one, numbers compare as numbers), so a Select that corrects its own value while it renders does not count as a change unless the value really differs.

**Saving.** `save()` blurs the focused input, waits as `frappe.app.trigger_primary_action` does and then for the Link checks that blur started, and posts the changed fields with the copy's `modified` to `data_steward.side_panel.save`. That endpoint refuses any key that is not a plain meta field (standard fields such as `docstatus` are not meta fields; tables and layout fields are `no_value_fields`), updates the document, sets `modified` to the copy's so `check_if_latest` refuses a stale copy as it does for the form, and saves it. It returns the new preview, which replaces the cached one.

**Permissions.** `data_steward.side_panel.get_preview` replaces `frappe.desk.doc_preview.get_preview` through `override_whitelisted_methods`. It calls Frappe's function and adds `write_permlevels`: none on a cancelled document or without write permission (`Document.has_permission`, so shares, user permissions and `has_permission` hooks count), none on a submitted one without submit permission (an update after submit checks it), otherwise `get_permlevel_access("write")`, the levels `validate_higher_perm_levels` lets a save change.

**Unsaved changes.** `open` (another document), `back` and `close` ask `frappe.warn` before they drop changes. Core calls `close()` on every route change and just before "Open in full page" routes, so `close()` tells them apart: when the route has already changed, it hands the changes to the document's form if that is where the route went (a one-time `form-refresh` handler that `frm.set_value`s them when `modified` still matches) and otherwise shows a toast; when it has not, it waits a tick and asks only if the URL has not moved. A `beforeunload` listener asks before a reload, except in developer mode, like the form's.

## Full width

`public/js/full_width.js` runs on every desk page. When the browser's `localStorage` has no `container_fullwidth` key, it sets it to `"true"` and calls `frappe.ui.toolbar.set_fullwidth_if_enabled()`. Frappe's own layout setting writes the same key, so a user's later choice wins.
