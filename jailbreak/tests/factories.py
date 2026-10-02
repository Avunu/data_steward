# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""Factories that return real, inserted documents. Everything here is
prefixed `_JB Test` so it is recognisable in a database someone is
debugging, and self-contained: `jailbreak` is a generic Frappe/ERPNext
add-on, so these do not import any other app's factories even when apps
share a bench's test site.

Documents post against the test site's default company (see `company()`),
purely because a test site needs one - not because `jailbreak` has any
opinion about it.
"""

from __future__ import annotations

from typing import Any, cast

import frappe
from frappe.utils import add_days, nowdate

PREFIX = "_JB Test"


def company() -> str:
	"""The test site's default company, or its only company if no default is set."""
	return cast(
		str,
		frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name"),
	)


def _insert(doc: Any, *, submit: bool = False) -> Any:
	doc.insert(ignore_permissions=True)
	if submit:
		doc.submit()
	return doc


def make_jailbreak_settings(**capabilities: int) -> Any:
	"""The Jailbreak Settings Single, with the given capabilities set.

	Capabilities not passed are left as they are - callers that need a known
	baseline should pass every capability they care about.
	"""
	settings = frappe.get_doc("Jailbreak Settings")
	for capability, value in capabilities.items():
		settings.set(capability, value)
	settings.save(ignore_permissions=True)
	return settings


def set_capability(capability: str, value: int) -> None:
	"""Set one Jailbreak Settings capability through `.save()`, so the
	`frappe.get_cached_doc` read inside `assert_capability`/`check_capability`
	actually sees it - a bare `.set()` with no save leaves the cached Single
	(and the database) untouched."""
	settings = frappe.get_doc("Jailbreak Settings")
	settings.set(capability, value)
	settings.save(ignore_permissions=True)


def make_customer(name: str = f"{PREFIX} Customer") -> Any:
	if frappe.db.exists("Customer", name):
		return frappe.get_doc("Customer", name)
	return _insert(
		frappe.get_doc({"doctype": "Customer", "customer_name": name, "customer_type": "Individual"})
	)


def make_item(item_code: str = f"{PREFIX}-Item", *, is_sales_item: int = 1, **fields: Any) -> Any:
	"""An Item. Idempotent on `item_code`."""
	if frappe.db.exists("Item", item_code):
		return frappe.get_doc("Item", item_code)
	return _insert(
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": fields.pop("item_name", item_code),
				"item_group": fields.pop("item_group", "All Item Groups"),
				"stock_uom": fields.pop("stock_uom", "Nos"),
				"is_stock_item": fields.pop("is_stock_item", 1),
				"is_sales_item": is_sales_item,
				**fields,
			}
		)
	)


def make_item_template(
	item_code: str = f"{PREFIX}-Template", *, attribute: str = "Colour", **fields: Any
) -> Any:
	"""A variant template Item with one attribute (`Colour`, an existing
	stock Item Attribute), for `hooks.item.convert_to_variant`."""
	if frappe.db.exists("Item", item_code):
		return frappe.get_doc("Item", item_code)
	return _insert(
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": fields.pop("item_group", "All Item Groups"),
				"stock_uom": fields.pop("stock_uom", "Nos"),
				"is_stock_item": 1,
				"has_variants": 1,
				"attributes": [{"attribute": attribute}],
				**fields,
			}
		)
	)


def make_sales_order(
	*, customer: str | None = None, item_code: str | None = None, submit: bool = True
) -> Any:
	"""A minimal, real Sales Order - `hooks.payment_request` needs a real
	reference document to attach a Payment Request to."""
	customer = customer or make_customer().name
	item_code = item_code or make_item().name
	warehouse = cast(str, frappe.db.get_value("Warehouse", {"company": company(), "is_group": 0}, "name"))
	so = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"customer": customer,
			"company": company(),
			"delivery_date": add_days(nowdate(), 7),
			"items": [{"item_code": item_code, "qty": 1, "rate": 100, "warehouse": warehouse}],
		}
	)
	return _insert(so, submit=submit)


def make_payment_request(*, reference: Any | None = None, **fields: Any) -> Any:
	reference = reference or make_sales_order()
	return _insert(
		frappe.get_doc(
			{
				"doctype": "Payment Request",
				"payment_request_type": fields.pop("payment_request_type", "Inward"),
				"reference_doctype": reference.doctype,
				"reference_name": reference.name,
				"party_type": "Customer",
				"party": reference.customer,
				"grand_total": reference.grand_total,
				**fields,
			}
		)
	)


def _bank_gl_account(name: str = f"{PREFIX} Bank") -> str:
	full_name = f"{name} - LC"
	if frappe.db.exists("Account", full_name):
		return full_name
	parent = cast(
		str,
		frappe.db.get_value("Account", {"company": company(), "account_type": "Bank", "is_group": 1}, "name"),
	)
	acc = _insert(
		frappe.get_doc(
			{
				"doctype": "Account",
				"company": company(),
				"account_name": name,
				"parent_account": parent,
				"account_type": "Bank",
				"is_group": 0,
			}
		)
	)
	return cast(str, acc.name)


def make_bank_account(name: str = f"{PREFIX} Checking") -> Any:
	"""A Bank Account, idempotent on its derived name (`<name> - <bank>`)."""
	bank_name = f"{PREFIX} Bank Co"
	if not frappe.db.exists("Bank", bank_name):
		_insert(frappe.get_doc({"doctype": "Bank", "bank_name": bank_name}))
	docname = f"{name} - {bank_name}"
	if frappe.db.exists("Bank Account", docname):
		return frappe.get_doc("Bank Account", docname)
	return _insert(
		frappe.get_doc(
			{
				"doctype": "Bank Account",
				"account_name": name,
				"bank": bank_name,
				"account": _bank_gl_account(),
				"company": company(),
			}
		)
	)


def make_bank_transaction(*, date: str = "2020-01-01", deposit: float = 100, **fields: Any) -> Any:
	bank_account = fields.pop("bank_account", None) or make_bank_account().name
	return _insert(
		frappe.get_doc(
			{
				"doctype": "Bank Transaction",
				"date": date,
				"bank_account": bank_account,
				"deposit": deposit,
				"currency": "USD",
				**fields,
			}
		)
	)


def make_journal_entry(*, amount: float = 25, **fields: Any) -> Any:
	account1 = _bank_gl_account()
	account2 = cast(
		str,
		frappe.db.get_value("Account", {"company": company(), "is_group": 0, "account_type": "Cash"}, "name"),
	)
	return _insert(
		frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"posting_date": fields.pop("posting_date", nowdate()),
				"company": company(),
				"accounts": [
					{"account": account1, "debit_in_account_currency": amount},
					{"account": account2, "credit_in_account_currency": amount},
				],
				**fields,
			}
		)
	)


def make_cleared_journal_entry(*, clearance_date: str = "2020-02-02", amount: float = 25) -> Any:
	"""A Journal Entry with a matching Bank Transaction that references it
	through its `payment_entries` child table, the shape
	`manually_clear_journal_entry` looks for."""
	je = make_journal_entry(amount=amount)
	make_bank_transaction(
		date=clearance_date,
		deposit=amount,
		description="clearance probe",
		payment_entries=[
			{"payment_document": "Journal Entry", "payment_entry": je.name, "allocated_amount": amount}
		],
	)
	return je


def make_note_with_version(*, original: str = "<p>original</p>", changed: str = "<p>changed</p>") -> Any:
	"""A real Note (`track_changes=1`, simple, no other-app
	dependency) edited once, so Frappe's own version-tracking writes a real
	Version row - the diff-shaped `data` `Version.restore()` actually has to
	deal with, not a hand-built one.

	Returns the Version doc (`version.docname` is the Note's name).
	"""
	note = _insert(frappe.get_doc({"doctype": "Note", "title": f"{PREFIX} Note", "content": original}))
	note.content = changed
	# `Document._save()` defaults `ignore_version` to `frappe.in_test` - under
	# the test runner that silently skips `save_version()` unless overridden.
	note.save(ignore_permissions=True, ignore_version=False)
	version_name = frappe.get_all(
		"Version",
		filters={"ref_doctype": "Note", "docname": note.name},
		order_by="creation desc",
		limit=1,
		pluck="name",
	)[0]
	return frappe.get_doc("Version", version_name)


def make_payment_entry(*, reference_no: str = "_JB-PROBE-1", **fields: Any) -> Any:
	paid_from = _bank_gl_account()
	paid_to = cast(
		str,
		frappe.db.get_value("Account", {"company": company(), "is_group": 0, "account_type": "Cash"}, "name"),
	)
	amount = fields.pop("paid_amount", 100)
	return _insert(
		frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": "Internal Transfer",
				"posting_date": fields.pop("posting_date", nowdate()),
				"company": company(),
				"paid_from": fields.pop("paid_from", paid_from),
				"paid_to": fields.pop("paid_to", paid_to),
				"paid_amount": amount,
				"received_amount": amount,
				"reference_no": reference_no,
				"reference_date": fields.pop("reference_date", nowdate()),
				**fields,
			}
		)
	)
