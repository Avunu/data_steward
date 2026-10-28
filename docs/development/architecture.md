---
title: How it works
description: How Data Steward gates each tool, and what each endpoint does on the server, from the capability check to the comment it leaves.
nav_title: How it works
order: 10
updated: 2026-10-26
---

Data Steward is one module, Data Steward, with one DocType, a desk bundle, three form scripts and five endpoints. It has no `doc_events`, no scheduled jobs, no server-side class overrides and no patches. Everything it changes, it changes when a user clicks a button.

## The capability gate

**Data Steward Settings** is a Single with one Check field per tool, all `0` by default. Two functions in `data_steward_settings.py` read it through `frappe.get_cached_doc`:

- `check_capability(capability)` returns `True` or `False` and never raises. The desk calls it through `data_steward.api.check_capability` before it adds a button; `window.data_steward.check_capability` in `public/js/data_steward.js` wraps the call in a promise that resolves `false` on any error.
- `assert_capability(capability)` raises `frappe.PermissionError` ("The {0} capability is not enabled.") when the tool is off, and `frappe.ValidationError` for a name it does not know. Every endpoint calls it first.

The second check is the role. `require_roles(*roles)` calls `frappe.only_for(roles, message=True)`, which lets the Administrator through and raises a permission error for a user with none of the roles. The third is the document permission, which each endpoint checks in its own way (below).

A tool being on says the tool is available on the site; the role and the permission say who may use it. The buttons only reflect the first: they are not hidden from users without the role.

## Bulk merge

`public/js/merge_records.js` replaces `frappe.views.ListView` with a subclass whose `setup_page` adds **Merge Selected** to the **Actions** menu, once per list view, when the DocType's meta has `allow_rename` and the tool is on. The desk bundle loads after Frappe's, so the base class is defined by then.

The dialog sends the DocType and one row per record to merge, `[<OLD_NAME>, <KEPT_NAME>, "true"]`, to `data_steward.data_steward.hooks.bulk_merge` (POST). After the capability and the System Manager check, it calls Frappe's `frappe.model.rename_doc.bulk_rename`. For each row that calls `rename_doc(..., merge=True)`, which checks write permission on both records and `allow_rename`, updates Link and Dynamic Link fields, moves attachments and versions, comments "merged … into …" on the kept record and deletes the old one (checking delete permission). `bulk_rename` commits after each successful row, rolls back a failed one, and returns one log line per row, which the desk shows in the **Merge Log** dialog. It refuses more than 500 rows.

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

## Full width

`public/js/full_width.js` runs on every desk page. When the browser's `localStorage` has no `container_fullwidth` key, it sets it to `"true"` and calls `frappe.ui.toolbar.set_fullwidth_if_enabled()`. Frappe's own layout setting writes the same key, so a user's later choice wins.
