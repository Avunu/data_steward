---
title: Install and upgrade
description: Install Data Steward on a Frappe v16 bench with ERPNext, see what the install sets up, upgrade it, move over from Jailbreak and uninstall it.
nav_title: Install
order: 1
updated: 2026-10-26
---

Data Steward installs like any Frappe app. It has no build step of its own beyond Frappe's asset build, no patches, and nothing to configure before the first use: every tool stays off until you enable it.

## Before you start

- A bench with Frappe v16 and a site that already has ERPNext v16 installed.
- A System Manager login on the site, to enable the tools afterwards.
- A recent backup, or a copy of the site to try corrections on first. A merge cannot be undone, and the other tools change submitted documents.

## Install

Run these from the bench directory. `<SITE_NAME>` is your site, for example `site1.example.com`.

```bash
bench get-app https://github.com/Avunu/data_steward --branch version-16
bench --site <SITE_NAME> install-app data_steward
```

`bench get-app` also builds the app's desk assets, unless you pass `--skip-assets`. The `version-16` branch holds the latest release for Frappe v16.

## What installing sets up

Installing the app creates the **Data Steward Settings** DocType, a Single in the Data Steward module, with all five check boxes unticked. It adds no custom fields, property setters, roles, records or scheduled jobs, and it has no patches.

The desk loads `data_steward.bundle.js` on every page and the form scripts for Item, Payment Entry and Journal Entry. They only add buttons when a tool is enabled, apart from the [full-width default](configuration.md#full-width-desk).

The app's `after_install` hook (`data_steward.install.after_install`) copies the tool settings from **Jailbreak Settings** when that DocType exists on the site. On a site that never had the old `jailbreak` app it does nothing.

## Coming from Jailbreak

Data Steward replaces the earlier `jailbreak` app. It has its own module and its own settings, so both can be installed on a site at the same time.

1. Install `data_steward` while `jailbreak` is still installed. The install copies the five check boxes from **Jailbreak Settings** to **Data Steward Settings**: **Allow Bulk Merge**, **Allow Convert to Variant**, **Set Clearance Date**, **Manually Clear** and **Remove Clearance**. A setting only the old app has is not copied.
2. Open **Data Steward Settings** and check the result.
3. Uninstall `jailbreak`.

Version restore, which `jailbreak` had already disabled, is not part of Data Steward.

## Upgrade

Update the app the way you update any Frappe app: `bench update`, or pull the new code in `apps/data_steward` and then run these from the bench directory.

```bash
bench build --app data_steward
bench --site <SITE_NAME> migrate
```

`bench migrate` syncs the **Data Steward Settings** DocType. The app has no patches, so an upgrade does not change your data, and the check boxes keep their values.

## Uninstall

```bash
bench --site <SITE_NAME> uninstall-app data_steward
```

Frappe takes a backup first (unless you pass `--no-backup`), then deletes the Data Steward module and the **Data Steward Settings** DocType with its values.

What the tools did stays: merged records stay merged, converted Items stay variants, clearance dates keep the value they were given, and the comments on those documents remain. The full-width setting stays in each browser that has it; switch it back under **Settings → Appearance → Layout**.

## Next

- [Configuration](configuration.md) explains each setting and lists everything the app adds to a site.
