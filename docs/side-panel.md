---
title: Edit in the side panel
description: Change a document in the desk's side panel and save it there, under the same field rules and permissions as its form.
nav_title: Side panel
order: 6
updated: 2026-11-02
---

Frappe 16.50 added a side panel to the desk: click a Link cell in a report view or a query report and the linked document opens in a drawer on the right, without leaving the report. Frappe shows the document there read-only. With Data Steward installed, you can change it in the panel and save it there.

## Before you start

- There is nothing to switch on. Like the [full-width default](configuration.md#full-width-desk), the editable side panel is not behind a setting.
- You can change what you could change in the document's form, and nothing more. The panel uses the form's own rules for each field, with your permissions on the document as the server reports them (see [Which fields you can change](#which-fields-you-can-change)).
- The side panel is part of Frappe 16.50 and later. On an older Frappe there is no panel, and this part of the app does nothing.

## Change a document

1. In a report view, for example **Task** → **Report View**, click a Link cell, such as a Task's **Project**. The Project opens in the side panel.
2. Change the fields you need. As soon as a value differs from the saved one, **Not Saved** replaces the document's status, and a **Save** button appears next to the panel's buttons. On a submitted document it reads **Update**.
3. Click **Save**, or press **Ctrl+S** (**Cmd+S** on a Mac) while the panel has the focus.

Only the fields you changed are sent. The server saves the document the normal way, so its validation, its hooks and its version history run as they do for the form. The panel then shows the document as it was saved, including any values the server set, and **Saved** appears at the bottom of the screen.

## Which fields you can change

The panel offers a field for editing when the form would:

- the document is a draft, or it is submitted and the field is **Allow on Submit**; a cancelled document cannot be changed;
- you have write permission on the document and on the field's permission level, and, on a submitted document, submit permission too;
- the field is not **Read Only**, a **Read Only** condition (`read_only_depends_on`) does not hold, and it is not **Set Only Once**;
- when the DocType has a workflow, your roles may edit documents in its current state.

**Mandatory Depends On** conditions are applied, and fields hidden by **Depends On** show and hide as you change values. A read-only field with no value is hidden, as on the form.

Child tables stay read-only: rows open in a dialog to read, but you cannot add, remove or change them in the panel. Use the form for that.

## Unsaved changes

The panel does not lose changes without saying so:

- **Close**, **Escape**, **Back**, or a click on another link while you have unsaved changes asks **Discard changes?** first. **Cancel** keeps you in the panel with your changes.
- **Open in full page** takes your changes with it: the form opens with them filled in and **Not Saved**, ready to save there.
- When you leave the page some other way, for example through the sidebar, the panel closes and a notice says that your changes were discarded.
- Reloading or closing the browser tab asks first, as the form does (except in developer mode).

## When someone else saved it first

The panel sends the time of the copy you edited along with your changes. When the document has been saved since, Frappe refuses the save with "has been modified after you have opened it", the same check the form makes, and your changes stay in the panel. To start again from the saved document, close the panel, choose **Discard**, and open the document again.

## Limits

The panel is not the form. It runs none of the DocType's form scripts, so:

- a Link field offers every record you may read. Filters a form script puts on it (`set_query`) do not apply here; filters set on the field in the DocType (**Link Filters**) do.
- values a form script fills in or recalculates when a field changes are not set in the panel. The server's own validation and its **Fetch From** fields do run when you save. Change fields that other fields depend on, such as a party on a transaction, in the form.
- Button fields are not shown, since what they do is a form script.

## Related

- [Limitations and troubleshooting](troubleshooting.md)
- [How it works](development/architecture.md#side-panel) for the code behind the panel
