<!-- Copyright (c) 2026, Avunu LLC and contributors
For license information, please see license.txt-->

### Data Steward

Audited data corrections for Frappe and ERPNext administrators.

Data Steward is a Frappe app of opt-in correction tools for the records the standard workflow cannot fix: merging duplicate records in any DocType, converting an existing Item into a variant of a template Item, and a few bank-clearance corrections (setting or removing a clearance date on a Payment Entry or Journal Entry). Installing the app does not switch any of these on. Each tool is disabled until a System Manager enables it, one capability at a time, in Data Steward Settings, and the server-side code re-checks the setting on every call, so hiding a button in the browser is not the only protection. Enabling a tool does not open it to every user either: each one also requires a role (see below) and the user's own write permission on the document, and every change leaves a comment on the document it touched. The one exception is the full-width layout, which is a cosmetic default for the desk UI (it is skipped if you have already chosen a container width) and does not touch any data.

## Features

Each tool is enabled on its own, and only for the roles listed.

### 🔀 Bulk Merge

- **Description**: Merge duplicate records in any DocType into one
- **Location**: "Merge Selected" action in every list view
- **Usage**: Select 2+ records in a list view and use the "Merge Selected" action
- **Requires**: System Manager

### 📦 Item Convert to Variant

- **Description**: Convert existing Items into variants of template Items
- **Location**: Item form → Actions → "Convert to Variant"
- **Usage**: Select a template item and specify attribute values to convert the current item
- **Requires**: Item Manager or System Manager, plus write permission on the Item

### 🏦 Clearance Date Corrections

- **Description**: Set a Payment Entry's clearance date; manually clear a Journal Entry against its matching Bank Transaction, or remove its clearance date
- **Location**: Payment Entry form → "Set Clearance Date"; Journal Entry form → Actions → "Manually Clear" / "Remove Clearance"
- **Requires**: Accounts Manager or System Manager, plus write permission on the document. Every change is recorded as a comment on the document.

### 🖥️ Full Width Interface

- **Description**: Automatically enables full-width container layout
- **Usage**: Automatically applied when the app is installed (no capability gate)

## Configuration

All capabilities (except full-width) must be explicitly enabled in **Data Steward Settings** before they become available to users. Changes to the settings are tracked.

Navigate to: **Setup → Data Steward Settings**

Toggle the capabilities you want to enable.

## Safeguards

- **Capability Gating**: Every correction requires explicit enablement
- **Permission Checks**: Backend validation ensures capabilities are enabled, and that the user holds the required role and document permission, before execution
- **Error Handling**: Clear error messages when capabilities are disabled
- **Audit Trail**: Every correction adds a comment to the document it changed

## Coming from Jailbreak

Data Steward replaces the earlier `jailbreak` app. It has its own module and its own settings, so both can be installed on a site at once: install `data_steward`, then uninstall `jailbreak`. On install, Data Steward copies the capability toggles from Jailbreak Settings. Version restore, which `jailbreak` had already disabled, is not part of Data Steward.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
bench get-app https://github.com/Avunu/data_steward.git
bench install-app data_steward
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/data_steward
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

MIT, Copyright (c) 2026 Avunu LLC. See [license.txt](license.txt).
