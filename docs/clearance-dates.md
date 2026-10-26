---
title: Correct clearance dates
description: Set or change the clearance date of a submitted Payment Entry, and clear or unclear a submitted Journal Entry against its Bank Transaction.
nav_title: Clearance dates
order: 5
updated: 2026-10-26
---

ERPNext sets the **Clearance Date** of a Payment Entry or Journal Entry through its Bank Clearance and bank reconciliation tools, and the field is read-only on the form. When reconciliation got a date wrong, or matched an entry without clearing it, these tools let an accounts manager correct it on the submitted entry.

## Before you start

- A System Manager must tick the tool in **Data Steward Settings**: **Set Clearance Date** for Payment Entry, **Manually Clear** and **Remove Clearance** for Journal Entry. See [Configuration](configuration.md).
- You need the Accounts Manager or System Manager role and write permission on the entry.
- The entry must be submitted. The buttons are not shown on a draft or a cancelled entry, and the server refuses one.

A clearance date before the entry's cheque date is refused, as in ERPNext's Bank Clearance tool. The cheque date is **Cheque/Reference Date** on a Payment Entry and **Reference Date** on a Journal Entry. A clearance date on the cheque date itself is allowed, and an entry without a cheque date takes any date.

## Set a Payment Entry's clearance date

1. Open the submitted Payment Entry.
2. Click **Set Clearance Date**.
3. In the **Set Clearance Date** dialog, pick the date in **Clearance Date**. It starts with the entry's current clearance date, and the days before the **Cheque/Reference Date** are greyed out.
4. Click **Set**.

A message confirms it: "Payment Entry `<NAME>` clearance date set to `<DATE>`." Reload the form to see the new date in **Clearance Date**.

**Clearance Date** is required in the dialog, so this tool changes a Payment Entry's clearance date but cannot remove it.

## Clear a Journal Entry from its Bank Transaction

**Manually Clear** uses the date of the Bank Transaction the Journal Entry is matched to: a Bank Transaction whose **Payment Entries** table has a row for this Journal Entry, as bank reconciliation creates when it matches the two.

1. Open the submitted Journal Entry.
2. Click **Actions → Manually Clear**.

When a matching Bank Transaction is found and its date is not before the **Reference Date**, the clearance date is set to the transaction's **Date** and a message says "Journal Entry `<NAME>` cleared to `<DATE>`." Reload the form to see it. When none is found, the message is "No matching bank transaction found." and nothing changes.

If more than one Bank Transaction lists the Journal Entry, the date of whichever one the database returns first is used. Check the result when an entry was split across transactions.

## Remove a Journal Entry's clearance date

1. Open the submitted Journal Entry.
2. Click **Actions → Remove Clearance**.

The clearance date is emptied and a message says "Journal Entry `<NAME>` clearance date removed." Reload the form to see the change.

## The audit trail

Every change adds a comment to the entry, "Clearance Date changed from `<OLD_DATE>` to `<NEW_DATE>`", with "(none)" for an empty date. The comment is in the entry's activity, below the form.

> [!WARNING]
> The date is checked against the cheque date only, and then written straight to the database. The entry's own validation does not run, and ERPNext does not re-check the date against the bank account, the Bank Transaction or the Bank Reconciliation. The Bank Transaction itself is not changed.

## Related

- [Limitations and troubleshooting](troubleshooting.md)
