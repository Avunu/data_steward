---
title: Data Steward
description: Merge duplicate records, convert Items to variants and correct bank clearance dates in ERPNext, each tool off until an administrator enables it.
nav_title: Overview
order: 0
updated: 2026-11-07
---

Frappe and ERPNext make some corrections hard on purpose. A duplicate Customer cannot be folded into another from its form, an Item cannot become a variant once it exists, and the clearance date of a submitted Payment Entry or Journal Entry cannot be edited. Data Steward adds a small set of tools for the administrator who cleans up real data and does need to make those changes.

Every tool is off until a System Manager enables it in **Data Steward Settings**, each one also needs a role and write permission on the document, and every change leaves a comment on the document it touched. The app also makes two changes to the desk that are not behind a setting: the side panel becomes editable, and the desk defaults to full width. Data Steward runs on Frappe v16 with ERPNext and is free software under the [MIT licence](../license.txt).

## What you get

### Bulk merge

A **Merge Selected** action in the list view of every DocType that allows renaming. Tick two or more records, pick the one to keep, and Frappe's own rename-and-merge folds the others into it. See [Merge duplicate records](merge-records.md).

![Three duplicate Customers ticked in the list view, and the Merge Records dialog asking which one to keep](screenshots/merge-records-light.webp)

### File merge

A **Merge Files** action in the File Manager and **Actions → Merge into...** on a file fold duplicate files into one. Every Attach field, rich-text field and link that used a duplicate uses the kept file instead, and the duplicates and their unused content are removed, also for files the cloud_storage app keeps in S3. See [Merge duplicate files](file-merge.md).

### Convert an Item to a variant

**Actions → Convert to Variant** on the Item form makes an existing Item a variant of a template Item, with a value for each of the template's attributes. See [Convert an Item to a variant](convert-to-variant.md).

![An existing Item being converted into a variant of the Classic T-Shirt template, with its colour and size picked](screenshots/convert-to-variant-light.webp)

### Clearance date corrections

A **Set Clearance Date** button on a submitted Payment Entry, and **Actions → Manually Clear** and **Actions → Remove Clearance** on a submitted Journal Entry. A clearance date before the entry's cheque date is refused, as in ERPNext's Bank Clearance tool. See [Correct clearance dates](clearance-dates.md).

### Settings and an audit trail

One check box per tool in **Data Steward Settings**, all off after install. Each correction adds a comment to the document it changed, and the settings record their own changes. See [Configuration](configuration.md).

![Data Steward Settings, with one check box for each tool](screenshots/settings-light.webp)

### Edit in the side panel

The document Frappe's side panel shows when you click a Link cell in a report can be changed and saved right there, under the same field rules and permissions as its form. Child tables stay read-only, and form scripts do not run in the panel. See [Edit in the side panel](side-panel.md).

### A full-width desk

The desk uses the full width of the screen in a browser that has no width stored yet. Like the editable side panel, it is not behind a setting; it changes no data. See [Configuration](configuration.md#full-width-desk).

## Where to start

| You are                               | Read                                                                                 |
| ------------------------------------- | ------------------------------------------------------------------------------------ |
| The administrator setting it up       | [Install and upgrade](install.md), then [Configuration](configuration.md)            |
| A System Manager cleaning up records  | [Merge duplicate records](merge-records.md)                                          |
| A System Manager cleaning up files    | [Merge duplicate files](file-merge.md)                                               |
| An Item Manager fixing the item list  | [Convert an Item to a variant](convert-to-variant.md)                                |
| An Accounts Manager fixing clearances | [Correct clearance dates](clearance-dates.md)                                        |
| Anyone working from report views      | [Edit in the side panel](side-panel.md)                                              |
| Anyone hitting an error               | [Limitations and troubleshooting](troubleshooting.md)                                |
| A developer changing the app          | [Development](development/README.md) and [How it works](development/architecture.md) |

## Requirements

- A bench with Frappe v16. The app declares `frappe >=16.0.0,<17.0.0`.
- ERPNext v16 (`erpnext >=16.0.0,<17.0.0`) on the same site. `hooks.py` lists it in `required_apps`, so install ERPNext first and Data Steward after it.
- A System Manager to switch the tools on, and users with the roles each tool needs: System Manager for bulk merge and file merge, Item Manager for Convert to Variant, Accounts Manager for the clearance tools.

> [!NOTE]
> These pages describe the code in the repository. Where a statement depends on Frappe's or ERPNext's own behaviour, it was checked against Frappe 16.52 and ERPNext 16.51.

## Source and changes

The source is at [github.com/Avunu/data_steward](https://github.com/Avunu/data_steward). Each release is listed on the [releases page](https://github.com/Avunu/data_steward/releases), and the [changelog](../CHANGELOG.md) lists every change.
