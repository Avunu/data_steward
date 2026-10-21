# Development

`nix develop` (or direnv) gives you Node, yarn, the git hooks and a dev bench with ERPNext.

| Command                    | What it does                                                                                       |
| -------------------------- | -------------------------------------------------------------------------------------------------- |
| `prek run --all-files`     | Runs the git hooks CI runs (ruff, oxlint, oxfmt and the rest)                                      |
| `yarn typecheck`           | Type-checks the desk scripts and the screenshot spec                                               |
| `yarn typecheck:py`        | Runs ty on the Python code                                                                         |
| `frappe-test --reuse-site` | Runs the tests on the dev site, with the coverage gate                                             |
| `frappe-shots`             | Rebuilds the demo site (`data_steward/demo.py`) and retakes the screenshots in `docs/screenshots/` |

## Where things live

- `data_steward/data_steward/doctype/data_steward_settings/`: the Single that holds one check box per tool, plus `assert_capability`, `check_capability` and `require_roles`.
- `data_steward/api.py`: the whitelisted `check_capability` the desk asks before it shows a tool.
- `data_steward/data_steward/hooks/`: the endpoints, one module per tool. `__init__.py` is bulk merge; `item.py`, `payment_entry.py` and `journal_entry.py` are the form tools.
- `data_steward/public/js/`: the desk bundle (`data_steward.bundle.js`: the capability helper, the list view override for **Merge Selected**, and the full-width default) and the form scripts for Item, Payment Entry and Journal Entry.
- `data_steward/install.py`: copies the toggles from Jailbreak Settings on install.
- `data_steward/demo.py`: the demo data for the screenshots.
- `types/`: the DocType types and the app's own desk globals, for `yarn typecheck`.
- `marketplace/`: the marketplace listing and the screenshot spec.

## Adding a tool

1. Add a check box to Data Steward Settings, and its fieldname to `capability_name` and `capabilities` in `data_steward_settings.py` and to `DataStewardCapability` in `types/data_steward.augment.d.ts`.
2. Start the endpoint with `assert_capability(...)`, then `require_roles(...)` and a permission check on the document. Accept POST only, do not commit, and add a comment to the document it changes.
3. In the desk, show the button only when `data_steward.check_capability(...)` resolves true.
4. If the old `jailbreak` app had the same toggle, add it to `CAPABILITY_FIELDS` in `install.py`.

## Tests

The tests live next to the code they cover (`test_*.py`) and in `data_steward/tests/`. Every test class extends `DataStewardIntegrationTestCase`, which stubs `frappe.db.commit` (Frappe's `bulk_rename` commits per row) and rolls back after the class. `data_steward/tests/factories.py` makes the Items, bank accounts, Bank Transactions, Payment Entries and Journal Entries the tests need, all named with a `_DS Test` prefix. The coverage gate is 95 %.
