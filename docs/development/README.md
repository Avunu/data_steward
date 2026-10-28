---
title: Develop Data Steward
description: The dev shell, the commands and tests, CI and the release flow of the Data Steward repository, and how to add a tool.
nav_title: Development
order: 9
updated: 2026-10-26
---

This page is for people changing the app. [How it works](architecture.md) explains the code behind each tool. The managed files, the shared checks and the release flow are described once for every Avunu app in the [app standards documentation](https://docs.avunu.net/frappe-nix/docs/app-standards/); this page covers what is specific to this repository.

## Set up

The repository is a frappe-nix app. `nix develop --no-pure-eval` (or `direnv allow`) gives you Python, Node, yarn, the git hooks and a dev bench with Frappe and ERPNext in `.frappe-nix/bench`.

```bash
nix develop --no-pure-eval
prek install
frappe-test
```

## Commands

Run these inside the dev shell, from the repository root.

| Command                                           | What it does                                                                                          |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `prek run --all-files`                            | Runs the git hooks CI runs: ruff, oxlint, oxfmt, Frappe's `test_utils` hooks and the rest             |
| `yarn typecheck`                                  | Type-checks the desk scripts and the screenshot spec with TypeScript                                  |
| `yarn typecheck:py`                               | Runs ty on the Python code against the dev bench                                                      |
| `frappe-test --reuse-site`                        | Runs the tests on the dev site, with the coverage gate                                                |
| `frappe-shots`                                    | Rebuilds the demo site from `data_steward/demo.py` and retakes the screenshots in `docs/screenshots/` |
| `nix run --no-pure-eval .#frappe-init -- --check` | Checks that the files frappe-nix manages are unchanged                                                |

## Where things live

```text
data_steward/
  hooks.py                       app hooks: the desk bundle, form scripts, after_install
  api.py                         whitelisted check_capability and assert_capability for the desk
  install.py                     after_install: copies the toggles from Jailbreak Settings
  demo.py                        demo data for frappe-demo and the screenshots
  data_steward/
    doctype/data_steward_settings/   the Single, plus assert_capability, check_capability, require_roles
    hooks/
      __init__.py                bulk_merge
      item.py                    convert_to_variant
      payment_entry.py           set_clearance_date
      journal_entry.py           manually_clear_journal_entry, remove_clearance_date_journal_entry
      clearance.py               the cheque-date check both clearance tools share
  public/js/
    data_steward.bundle.js       the desk bundle: data_steward.js, merge_records.js, full_width.js
    item.js, payment_entry.js, journal_entry.js   the form scripts
  tests/                         the shared test case, factories, install and demo tests
types/                           DocType types and the app's desk globals, for yarn typecheck
marketplace/                     the marketplace listing and the screenshot spec
```

## Tests

The tests live next to the code they cover (`test_*.py`) and in `data_steward/tests/`. Every test class extends `DataStewardIntegrationTestCase` (`data_steward/tests/__init__.py`). Its `capability_enabled(...)` context manager switches one tool on for the length of a test, and it stubs `frappe.db.commit`, because Frappe's `bulk_rename` commits after each row, and rolls back after the class. `data_steward/tests/factories.py` makes the Items, bank accounts, Bank Transactions, Payment Entries and Journal Entries the tests need, all named with a `_DS Test` prefix.

`test_write_contract.py` checks the rules every endpoint follows: the endpoints that change data accept POST only, they leave the commit to the request, and an error after the write rolls it back. The coverage floor is `fail_under = 95` in `pyproject.toml`.

Frappe only runs tests on a site that allows them. Outside the dev shell, use a development or test site, never production:

```bash
bench --site <TEST_SITE> set-config allow_tests true
bench --site <TEST_SITE> run-tests --app data_steward
```

There are no JavaScript unit tests. `yarn typecheck` and the oxlint and oxfmt hooks are the front-end gates.

## Continuous integration and releases

`.github/workflows/ci.yml` is managed by frappe-nix and runs the shared gates on every pull request, every push to `develop` and once a day: `ci / lint`, `ci / typecheck`, `ci / test` and `ci / marketplace`. `pr-policy.yml` checks a pull request's base, title and commits; pull requests go to `develop` with conventional commit titles. `nightly.yml` runs the integration suites each night and is never a required check.

`release.yml` runs release-please on `develop`. Merging its release pull request tags the version, updates `CHANGELOG.md`, `package.json` and `data_steward/__init__.py`, and moves the `version-16` branch forward; that is the branch `bench get-app` installs. Dependabot updates the dependencies in groups, and `deps.yml` relocks after a flake bump.

## Adding a tool

1. Add a check box to Data Steward Settings, and its fieldname to `capability_name` and `capabilities` in `data_steward_settings.py` and to `DataStewardCapability` in `types/data_steward.augment.d.ts`.
2. Start the endpoint with `assert_capability(...)`, then `require_roles(...)` and a permission check on the document. Accept POST only, do not commit, and add a comment to the document it changes.
3. In the desk, show the button only when `data_steward.check_capability(...)` resolves true.
4. If the old `jailbreak` app had the same toggle, add it to `CAPABILITY_FIELDS` in `install.py`.
5. Add tests, and the endpoint to `test_write_contract.py`, and describe the tool in these pages and the README.

## Working on these docs

The documentation is Markdown in `docs/`. It is published with the other Avunu projects at [docs.avunu.net/data-steward/docs/](https://docs.avunu.net/data-steward/docs/) by [Avunu/site-docs](https://github.com/Avunu/site-docs), which picks up the latest release of this repository. The `Docs` workflow (`.github/workflows/docs.yml`) checks a pull request that touches `docs/` the way the site builds it. Write the files so that they read well on GitHub too: front matter, GitHub alerts and relative links, as the [writing guide](https://github.com/Avunu/site-docs/blob/main/docs/guide/writing-docs.md) describes. The screenshots in `docs/screenshots/` are generated by `frappe-shots`; do not edit them by hand.

To check a change as the pull request check does, clone Avunu/site-docs beside this repository and, from its folder, run:

```bash
npm ci --ignore-scripts && npm run build
node build/cli.js check --only data-steward --source data-steward=../data_steward
```
