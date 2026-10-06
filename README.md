<img src="https://github.com/user-attachments/assets/f0aa1054-51c1-41b3-b5ea-0111b1c67aef" alt="Deranged Frappe Barista" width="300">

### Jailbreak

Add destructive superpowers to any Frappe site.

Jailbreak is a Frappe app of opt-in administrative power tools for the cases where the standard guardrails get in the way: global bulk merge of records in any DocType, converting an existing Item into a variant of a template Item, restoring documents from their version history (currently disabled), and a few bank-clearance corrections (setting or removing a clearance date on a Payment Entry or Journal Entry). Installing the app does not switch any of these on. Each tool is disabled until a System Manager enables it, one capability at a time, in Jailbreak Settings, and the server-side code re-checks the setting on every call, so hiding a button in the browser is not the only protection. Enabling a tool does not open it to every user either: each one also requires a role (see below) and the user's own write permission on the document. The one exception is the full-width layout, which is a cosmetic default for the desk UI (it is skipped if you have already chosen a container width) and does not touch any data.

## Features

Jailbreak is a collection of various hacks, mods, and anti-features you probably don't want enabled on your Frappe sites... but if you do, they can be individually enabled in all their perilous grandeur:

### 🔀 Global Bulk Merge
- **Description**: Merge multiple records across any DocType
- **Location**: Available as "Merge Selected" action in all list views
- **Usage**: Select 2+ records in any list view and use the "Merge Selected" action
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

### 🔄 Version Restore (temporarily disabled)
- **Description**: Restore documents from their version history. Currently disabled: it reported success without reverting anything, and is being rewritten.
- **Location**: Version list view and individual Version forms
- **Usage**: 
  - **List View**: Select versions and use "Restore" bulk action
  - **Form View**: Click "Restore" button on individual versions

### 🖥️ Full Width Interface
- **Description**: Automatically enables full-width container layout
- **Usage**: Automatically applied when the app is installed (no capability gate)

## Configuration

All capabilities (except full-width) must be explicitly enabled in **Jailbreak Settings** before they become available to users.

Navigate to: **Setup → Jailbreak Settings**

Toggle the capabilities you want to enable.

## Safety Features

- **Capability Gating**: All destructive operations require explicit enablement
- **Permission Checks**: Backend validation ensures capabilities are enabled, and that the user holds the required role and document permission, before execution
- **Error Handling**: Clear error messages when capabilities are disabled
- **Audit Trail**: All operations create proper audit trails and comments

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
bench get-app https://github.com/Avunu/jailbreak.git
bench install-app jailbreak
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/jailbreak
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

MIT, Copyright (c) 2026 Avunu LLC. See [license.txt](license.txt).
