# Data Steward

Merge duplicate records, convert Items to variants and fix bank clearance dates

Frappe and ERPNext make some corrections hard on purpose. Data Steward adds a small set of tools for the administrator who does need to make them: merging duplicate records, converting an existing Item into a variant of a template, and correcting the clearance date of a Payment Entry or Journal Entry. Every tool is off until a System Manager enables it, each one needs a role and write permission on the document, and every change leaves a comment on the document it touched.

## What you get

- **Bulk merge.** A **Merge Selected** action in the list view of every DocType that allows renaming: tick two or more records, pick the one to keep, and the others are merged into it with Frappe's own rename-and-merge. A merge log then shows which records were merged and which failed. System Manager only.
- **Convert an Item to a variant.** **Actions → Convert to Variant** on the Item form: choose a template Item and a value for each of its attributes. Item Manager or System Manager.
- **Payment Entry clearance date.** A **Set Clearance Date** button on a submitted Payment Entry. Accounts Manager or System Manager.
- **Journal Entry clearance.** On a submitted Journal Entry, **Actions → Manually Clear** sets the clearance date from the Bank Transaction the entry is matched to; **Actions → Remove Clearance** clears it again. Accounts Manager or System Manager.
- **Full-width desk.** The desk uses the full screen width unless the user has already chosen a container width. This is the one part that is not behind a setting, and it changes no data.

## Setting it up

Open **Data Steward Settings** as a System Manager and tick only the tools you need. Buttons for a tool that is off are not shown, and the server refuses its calls. Try a correction on a copy of the site first.

## Limitations

- Clearance changes are written straight to the database, so ERPNext does not re-check them against the reconciliation.

## Coming from Jailbreak

Data Steward replaces the earlier `jailbreak` app. Install `data_steward`, then uninstall `jailbreak`: on install, Data Steward copies the capability toggles from Jailbreak Settings. Version restore, which `jailbreak` had already disabled, is not part of Data Steward.

## Installation

Data Steward needs ERPNext on the same site.

```bash
bench get-app https://github.com/Avunu/data_steward --branch version-16
bench --site <site> install-app data_steward
```

## Development

The source layout, the tests and how to add a tool are described in [Development](development.md).

## License

[MIT](https://github.com/Avunu/data_steward/blob/develop/license.txt), Copyright (c) 2025–present Avunu LLC.
