---
title: Limitations and troubleshooting
description: What Data Steward's tools do not do, and the messages they show, with the cause and the fix for each.
nav_title: Troubleshooting
order: 8
updated: 2026-10-26
---

## Limitations

- **Clearance changes skip the document's own validation.** The date is checked the way ERPNext's Bank Clearance tool checks it, not before the cheque date, and then written straight to the database. ERPNext does not re-check it against the bank account, the Bank Transaction or the Bank Reconciliation.
- **A Payment Entry's clearance date cannot be removed.** **Set Clearance Date** requires a date. Only a Journal Entry has **Remove Clearance**.
- **Manually Clear takes the first match.** When more than one Bank Transaction lists a Journal Entry, the date of whichever one the database returns first is used.
- **The form is not reloaded after a clearance change.** Reload it to see the new **Clearance Date**.
- **A merge cannot be undone.** The merged records are deleted, and their own field values and child table rows are not copied to the record you keep. At most 500 records can be merged in one run, and a submitted document cannot be merged.
- **Convert to Variant copies only the attributes and the stock unit.** Nothing else comes from the template, and ERPNext's check for another variant with the same attribute values does not run on a converted Item. A template based on Manufacturer, or one with a numeric attribute, cannot be used.
- **Buttons do not check roles.** While a tool is enabled, its button is shown to everyone who can open the form or list; the server refuses the call from a user without the role.
- **The full-width default has no setting.** It applies in every browser that has no layout stored yet. Each user can switch back to **Compact** in Frappe's layout setting.

## Troubleshooting

### A tool's button is missing

The tool is off in **Data Steward Settings**, or the document is not in a state the tool works on. Check that:

- the tool's check box is ticked in **Data Steward Settings** (see [Configuration](configuration.md));
- for **Merge Selected**, the DocType has **Allow Rename** set, and you ticked at least one row so the **Actions** menu shows;
- for **Convert to Variant**, the Item is saved;
- for the clearance tools, the entry is submitted.

The desk asks whether a tool is enabled when the form or list loads. After changing a setting, reload the page.

### "The Bulk Merge capability is not enabled."

The tool is off in **Data Steward Settings**, possibly switched off while the page was open. The other tools give the same message with their own name: "The Convert to Variant capability is not enabled.", "The Payment Entry Set Clearance Date capability is not enabled.", "The Journal Entry Manually Clear capability is not enabled." and "The Journal Entry Remove Clearance capability is not enabled."

Fix: ask a System Manager to tick the tool in **Data Steward Settings**.

### "This action is only allowed for System Manager"

The message comes from Frappe, under the title **Not Permitted**, and names the roles the tool accepts: System Manager for bulk merge, Item Manager or System Manager for Convert to Variant, Accounts Manager or System Manager for the clearance tools.

Fix: give the user one of those roles, or have someone who has one make the change.

### A permission error naming the document

You have the role, but not write permission on this document. For a merge, the failure is a line in the **Merge Log** instead, such as "You need write permission on Customer `<NAME>` to merge", and a merge also needs delete permission on each record being merged.

Fix: give the user's role write (and for merging, delete) permission on the DocType in the Role Permission Manager, or check the user permissions that restrict this record.

### "Only a submitted Payment Entry can have a clearance date."

Or "Only a submitted Journal Entry can have a clearance date." The entry is a draft or cancelled. Bank clearance applies to submitted entries only.

Fix: submit the entry first. A cancelled entry cannot be cleared; clear its amendment instead.

### "Clearance date `<DATE>` must be after cheque date `<DATE>`."

Shown under the title **Invalid Clearance Date**. The clearance date is before the entry's **Cheque/Reference Date** (Payment Entry) or **Reference Date** (Journal Entry). For **Manually Clear**, the date is the matched Bank Transaction's, so the transaction is dated before the cheque.

Fix: pick a date on or after the cheque date. If the cheque date itself is wrong, correct it on the entry (cancel and amend), or check that the Bank Transaction matched to the Journal Entry is the right one.

### "No matching bank transaction found."

**Manually Clear** found no Bank Transaction whose **Payment Entries** table lists this Journal Entry. Nothing was changed.

Fix: match the Journal Entry to its Bank Transaction in ERPNext's bank reconciliation first, then click **Manually Clear** again.

### "Please select at least two records to merge."

You clicked **Merge Selected** with fewer than two rows ticked.

Fix: tick the duplicates and the record to keep, then try again.

### A "** Failed" line in the Merge Log

The line ends with the error Frappe raised for that record, and that record was left as it was. Common causes: missing write or delete permission, a submitted document (Frappe cannot delete it), or a rule of the DocType itself that refuses the rename. "Maximum 500 rows allowed" means you tried to merge more than 500 records at once.

Fix: correct the cause named in the line and merge that record again.

### "This template has no attributes."

The template you picked has no **Variant Attributes**, for example because its variants are based on Manufacturer.

Fix: choose a template with attributes, or add them to the template first.

### ERPNext refuses the converted Item

The Item is saved with ERPNext's Item validation, and whatever it refuses rolls the whole conversion back. Messages you can see include:

- "Item `<TEMPLATE>` is not a template item.": the template no longer has **Has Variants** ticked.
- "Default Unit of Measure for Item `<ITEM>` cannot be changed directly because you have already made some transaction(s) with another UOM. …": the Item's **Default Unit of Measure** differs from the template's, and the Item has stock transactions in its own unit. ERPNext does not allow changing it; create a new variant from the template instead.
- "Attribute `<ATTRIBUTE>` is disabled.": the attribute is disabled on the template's **Variant Attributes**.

Fix: correct the template or the Item as the message says, then convert again.

### The desk went full width

That is the app's [full-width default](configuration.md#full-width-desk). Switch to **Compact** in Frappe's layout setting; the app does not change it again in that browser.
