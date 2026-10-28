<!-- Copyright (c) 2026, Avunu LLC and contributors
For license information, please see license.txt-->

<!-- frappe-nix:begin header -->

<div align="center">

<img src="data_steward/public/images/data_steward-logo.svg" width="80" alt="">

# Data Steward

Merge duplicate records, convert Items to variants and fix bank clearance dates

[![CI](https://github.com/Avunu/data_steward/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/Avunu/data_steward/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/Avunu/data_steward)](https://github.com/Avunu/data_steward/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](license.txt)
[![Frappe v16](https://img.shields.io/badge/Frappe-v16-blue)](https://github.com/frappe/frappe/tree/version-16)
[![Documentation](https://img.shields.io/badge/docs-docs.avunu.net-blue)](https://docs.avunu.net/data-steward/)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/merge-records-dark.webp">
  <img src="docs/screenshots/merge-records-light.webp" alt="Three duplicate Customers ticked in the list view, and the Merge Records dialog asking which one to keep">
</picture>

</div>

<!-- frappe-nix:end header -->

## Overview

Frappe and ERPNext make some corrections hard on purpose: a duplicate Customer can't be folded into another from its form, an Item can't become a variant once it exists, and a clearance date that bank reconciliation got wrong can't be changed on a submitted entry. Sometimes an administrator cleaning up real data does need to make those changes. Data Steward adds a small set of tools for them.

Installing the app switches none of the tools on. Each one stays off until a System Manager enables it in **Data Steward Settings**, the server checks that setting again on every call, each tool also needs a role and the user's write permission on the document, and every change leaves a comment on the document it touched. It is meant for experienced administrators; try a correction on a copy of the site first.

Full documentation: [docs.avunu.net/data-steward/docs/](https://docs.avunu.net/data-steward/docs/).

## Features

- **Bulk merge.** A **Merge Selected** action in the list view of every DocType that allows renaming: tick two or more records, pick the one to keep, and the others are merged into it with Frappe's own rename-and-merge. System Manager only. See [docs/merge-records.md](docs/merge-records.md).
- **Convert an Item to a variant.** **Actions → Convert to Variant** on the Item form: choose a template Item, pick a value for each of its attributes, and the Item becomes a variant of that template. Item Manager or System Manager. See [docs/convert-to-variant.md](docs/convert-to-variant.md).
- **Payment Entry clearance date.** A **Set Clearance Date** button on a submitted Payment Entry sets or changes the date in a dialog. As in ERPNext's Bank Clearance tool, the date can't be before the entry's Cheque/Reference Date. Accounts Manager or System Manager.
- **Journal Entry clearance.** **Actions → Manually Clear** on a submitted Journal Entry sets the clearance date to the date of the Bank Transaction the entry is matched to, and refuses it when that date is before the entry's Reference Date (cheque date); **Actions → Remove Clearance** clears it again. Accounts Manager or System Manager. See [docs/clearance-dates.md](docs/clearance-dates.md).
- **An audit trail.** Every correction adds a comment to the document it changed: the old and new clearance date, the template an Item was converted to, or (Frappe's own) the records merged into the one kept. Data Steward Settings tracks its own changes too.
- **Full-width desk.** The desk uses the full screen width in a browser that has no layout stored yet; Frappe keeps that choice per browser, not per user. This is the one part of the app that is not behind a setting, and it changes no data.

<!-- frappe-nix:begin compatibility -->

## Compatibility

| Frappe | Branch       |
| ------ | ------------ |
| v16    | `version-16` |

| Requires                                     | Version            |
| -------------------------------------------- | ------------------ |
| [erpnext](https://github.com/frappe/erpnext) | `>=16.0.0,<17.0.0` |

<!-- frappe-nix:end compatibility -->

<!-- frappe-nix:begin installation -->

## Installation

```bash
bench get-app https://github.com/Avunu/data_steward --branch version-16
bench --site <site> install-app data_steward
```

<!-- frappe-nix:end installation -->

Data Steward needs ERPNext on the same site.

## Configuration

Open **Data Steward Settings** (search for it in the awesome bar) as a System Manager and tick only the tools you need:

| Setting                  | Tool                                       | Who can use it                   |
| ------------------------ | ------------------------------------------ | -------------------------------- |
| Allow Bulk Merge         | Merge Selected, in renamable list views    | System Manager                   |
| Allow Convert to Variant | Item → Actions → Convert to Variant        | Item Manager, System Manager     |
| Set Clearance Date       | Payment Entry → Set Clearance Date         | Accounts Manager, System Manager |
| Manually Clear           | Journal Entry → Actions → Manually Clear   | Accounts Manager, System Manager |
| Remove Clearance         | Journal Entry → Actions → Remove Clearance | Accounts Manager, System Manager |

Every tool also needs one of its roles and write permission on the document; a merge also needs delete permission on the records merged. Buttons for a tool that is switched off are not shown, and its endpoint refuses the call. Each setting, role and permission is described in [docs/configuration.md](docs/configuration.md).

**Coming from Jailbreak.** Data Steward replaces the earlier `jailbreak` app. Install `data_steward` while `jailbreak` is still installed, so the install copies the five toggles from Jailbreak Settings, then uninstall `jailbreak`. See [docs/install.md](docs/install.md#coming-from-jailbreak).

## How It Works

- Every endpoint first checks that its tool is on in **Data Steward Settings** (`assert_capability`), then the role, then the user's permission on the document. The desk asks `data_steward.api.check_capability` before it shows a button.
- **Bulk merge** extends the desk's `ListView` class to add **Merge Selected**, and calls Frappe's `bulk_rename` with the merge flag, so each record is merged, committed and logged on its own.
- **Convert to Variant** writes the set-once `variant_of` field directly, replaces the Item's attributes with the template's, takes the template's stock UOM when it differs, and saves the Item through ERPNext's validation.
- **The clearance tools** check the date against the cheque date, as ERPNext's Bank Clearance tool does, and write `clearance_date` directly on the submitted entry.
- The endpoints accept POST only and do not commit themselves: the request commits on success and rolls back on an error.

The details are in [docs/development/architecture.md](docs/development/architecture.md).

## Limitations

- **Clearance changes skip the document's own validation.** The date is checked the way ERPNext's Bank Clearance tool checks it (not before the cheque date), but it is then written straight to the database, so ERPNext does not re-check it against the bank account or the Bank Reconciliation.
- **A merge cannot be undone**, and the merged records' own field values are not copied to the record kept.
- **Convert to Variant copies only the attributes and the stock unit**, and ERPNext's check for an existing variant with the same attribute values does not run on a converted Item.

The full list, and the messages the tools show, are in [docs/troubleshooting.md](docs/troubleshooting.md).

<!-- frappe-nix:begin support -->

## Support

- Documentation: [docs.avunu.net/data-steward/](https://docs.avunu.net/data-steward/)
- Bug reports and questions: [GitHub issues](https://github.com/Avunu/data_steward/issues)
- E-mail: <mail@avu.nu>

<!-- frappe-nix:end support -->

<!-- frappe-nix:begin development -->

## Development

```bash
nix develop        # or: direnv allow
prek install       # the git hooks CI runs
frappe-test        # the tests, the way CI runs them
```

The managed files, checks and release flow are described in the [app standards documentation](https://docs.avunu.net/frappe-nix/docs/app-standards/).

<!-- frappe-nix:end development -->

The source layout, the tests and how to add a tool are described in [docs/development/README.md](docs/development/README.md).

<!-- frappe-nix:begin license -->

## License

MIT, Copyright (c) 2025–present Avunu LLC → [license.txt](license.txt)

<!-- frappe-nix:end license -->
