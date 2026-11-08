// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

// Makes the desk side panel (frappe/public/js/frappe/ui/side_panel.js, Frappe 16.50+) editable.
//
// Core shows the document in a frm-less frappe.ui.form.Layout and forces every control to "Read".
// Here the same Layout takes the form's own field rules instead: frappe.perm
// .get_field_display_status (permlevel, docstatus, allow on submit, read only, set only once) and
// the workflow state's edit roles, fed with the permlevels the server says the user may write
// (data_steward.side_panel.get_preview adds them to the preview). Edits go to a copy of the
// document, and Save sends only the changed fields, with the copy's `modified`, to
// data_steward.side_panel.save.
//
// Without a frm there are no form scripts: their link filters, fetches and recalculations do not
// run, and the server's validation is what checks a change. Child tables stay read-only.

/**
 * @typedef {import("frappe-types").BaseControl} BaseControl
 * @typedef {import("frappe-types").DisplayStatus} DisplayStatus
 * @typedef {import("frappe-types").DocField} DocField
 * @typedef {import("frappe-types").DocPreview} DocPreview
 * @typedef {import("frappe-types").FrappeDoc} FrappeDoc
 * @typedef {import("frappe-types").Form} Form
 * @typedef {import("frappe-types").Permission} Permission
 * @typedef {import("frappe-types").SidePanel} SidePanel
 */

/**
 * What frappe.desk.doc_preview.get_preview returns, with data_steward.side_panel's addition: the
 * permlevels the user may change.
 * @typedef {DocPreview & { write_permlevels?: number[] }} SidePanelPreview
 */

/**
 * frappe.ui.SidePanel with the members this file adds.
 * @typedef {SidePanel & {
 *   update_editing_state(): void,
 *   editor?: Editor,
 *   editors?: Record<string, Editor>,
 *   $save?: JQuery<HTMLElement>,
 *   $not_saved?: JQuery<HTMLElement>,
 *   saving?: boolean,
 *   opened_on?: { route: string, path: string },
 *   __data_steward_editable?: boolean,
 * }} EditableSidePanel
 */

const TABLE_FIELDTYPES = new Set(["Table", "Table MultiSelect"]);
// The form hides a read-only field without a value, except these (BaseControl.get_status).
const SHOWN_WHEN_EMPTY = new Set(["Attachment Gallery", "HTML", "Image", "Button", "Geolocation"]);
const NUMERIC_FIELDTYPES = new Set(["Int", "Float", "Currency", "Percent", "Check", "Rating", "Duration"]);

/** @param {unknown} value */
const is_empty = (value) => value === null || value === undefined || value === "";

/**
 * Whether two values of a field are the same, as the user sees them: a cleared field matches a
 * null one, and 1 matches "1".
 * @param {string | undefined} fieldtype
 * @param {unknown} a
 * @param {unknown} b
 */
function same_value(fieldtype, a, b) {
	if (fieldtype && NUMERIC_FIELDTYPES.has(fieldtype)) return flt(a) === flt(b);
	if (is_empty(a) && is_empty(b)) return true;
	return String(a) === String(b);
}

/**
 * The meta's docfields with child docfields on each table: frm-less, Grid.setup_fields() reads
 * them from df.fields (core's get_read_only_docfields, which side_panel.js keeps private).
 * @param {string} doctype
 * @returns {DocField[]}
 */
function get_docfields(doctype) {
	return (frappe.get_meta(doctype)?.fields || []).map((df) => {
		// A copy: the meta's own docfields must stay as they are.
		/** @type {DocField} */
		const clone = Object.assign({}, df, { parent: df.parent || doctype });
		if (TABLE_FIELDTYPES.has(df.fieldtype) && typeof df.options === "string" && df.options) {
			clone.fields = get_docfields(df.options);
		}
		return clone;
	});
}

/**
 * frappe.workflow.is_read_only, for a document that is not in locals.
 * @param {string} doctype
 * @param {FrappeDoc} doc
 */
function workflow_allows_edit(doctype, doc) {
	const state_field = frappe.workflow.get_state_fieldname(doctype);
	if (!state_field) return true;
	const state = doc[state_field] || frappe.workflow.get_default_state(doctype, doc.docstatus);
	if (!state) return true;
	const roles = frappe.workflow.get_document_state_roles(doctype, String(state));
	return frappe.user_roles.some((role) => roles.includes(role));
}

/**
 * A `depends_on`-style condition, or null when it cannot be judged here: a broken expression, or
 * an "fn:" one, which needs a frm. Unlike Layout.evaluate_depends_on_value it never throws.
 * @param {unknown} expression
 * @param {FrappeDoc} doc
 * @returns {boolean | null}
 */
function evaluate_condition(expression, doc) {
	if (typeof expression === "boolean") return expression;
	if (typeof expression !== "string" || expression.startsWith("fn:")) return null;
	if (expression.startsWith("eval:")) {
		try {
			return Boolean(frappe.utils.eval(expression.slice(5), { doc, parent: doc }));
		} catch {
			return null;
		}
	}
	const value = doc[expression];
	return Array.isArray(value) ? value.length > 0 : Boolean(value);
}

/** One Layout per doctype, like the panel's own; `load` points it at a document. */
class Editor {
	/**
	 * @param {EditableSidePanel} panel
	 * @param {string} doctype
	 * @param {FrappeDoc} doc the copy to edit, so a control that writes while it renders cannot
	 * touch the cached preview
	 */
	constructor(panel, doctype, doc) {
		this.panel = panel;
		this.doctype = doctype;
		this.doc = doc;
		/** @type {SidePanelPreview | null} */
		this.preview = null;
		/** @type {Permission[]} */
		this.perm = [];
		/** Fieldnames written since the document was loaded; get_changes() keeps the ones that differ. */
		this.changed = new Set();

		this.$wrapper = $('<div class="side-panel-doc"></div>').appendTo(panel.$body);
		this.layout = new frappe.ui.form.Layout({
			parent: this.$wrapper,
			doctype,
			// Explicit fields also avoid get_doctype_fields(), which needs a frm.
			fields: get_docfields(doctype),
			doc,
			card_layout: true,
		});
		this.layout.make();
		this.setup_layout();
		for (const field of this.layout.fields_list) {
			if (field instanceof frappe.ui.form.Control) this.setup_control(field);
		}
	}

	setup_layout() {
		const layout = this.layout;

		// Frm-less, Layout applies mandatory_depends_on and read_only_depends_on only in a dialog.
		layout.set_dependant_property = (condition, fieldname, property) => {
			const control = layout.fields_dict[fieldname];
			const value = evaluate_condition(condition, this.doc);
			if (!(control instanceof frappe.ui.form.Control) || value === null) return;
			if (cint(control.df[property]) === Number(value)) return;
			control.df[property] = Number(value);
			control.refresh();
		};

		// Link fetches its fetch_from values through this when there is no frm (link.js).
		layout.set_value = (fieldname, value) => {
			const control = layout.fields_dict[fieldname];
			if (control instanceof frappe.ui.form.Control) control.set_value(value);
		};
	}

	/** @param {BaseControl} control */
	setup_control(control) {
		control.get_status = () => this.get_status(control);

		// Frm-less, the base set_model_value writes into control.doc, which is this.doc.
		const set_model_value = control.set_model_value.bind(control);
		control.set_model_value = (value) => {
			const done = set_model_value(value);
			this.changed.add(control.df.fieldname);
			this.layout.refresh_dependency();
			this.panel.update_editing_state();
			return done;
		};

		if (control.df.fieldtype === "Link" || control.df.fieldtype === "Dynamic Link") {
			// Link refreshes the fetched fields through this.frm, which is not there; the layout's
			// set_value has set them through their own controls already.
			control.after_set_value = () => {};
		}
		if (control instanceof frappe.ui.form.ControlDynamicLink) {
			// Without a frm or a dialog, Dynamic Link looks for its doctype in locals or cur_list.
			const doctype_field = String(control.df.options || "");
			control.get_options = () => String(this.doc[doctype_field] ?? "");
		}
	}

	/**
	 * The form's rules for the field, with this document and the preview's permissions.
	 * @param {BaseControl} control
	 * @returns {DisplayStatus}
	 */
	get_status(control) {
		const df = control.df;
		if (cint(df.hidden) || cint(df.hidden_due_to_dependency)) return "None";
		// A permlevel the user cannot read: the server has blanked its values.
		if (!this.perm[cint(df.permlevel)]) return "None";
		// The form hides the series once the document is named (form.js refresh_fields).
		if (df.fieldname === "naming_series" && frappe.get_meta(this.doctype)?.autoname === "naming_series:") {
			return "None";
		}

		let status = frappe.perm.get_field_display_status(df, this.doc, this.perm);
		// Rows are added, moved and removed through a frm, and a Button runs a form script.
		if (status === "Write" && (TABLE_FIELDTYPES.has(df.fieldtype) || df.fieldtype === "Button")) {
			status = "Read";
		}
		if (
			status === "Read" &&
			is_empty(this.doc[df.fieldname]) &&
			!SHOWN_WHEN_EMPTY.has(df.fieldtype) &&
			frappe.defaults.is_enabled("hide_empty_read_only_fields")
		) {
			status = "None";
		}
		return status;
	}

	/**
	 * @param {SidePanelPreview} preview
	 * @param {FrappeDoc} doc a copy of preview.doc, which stays as loaded for Back and a revisit
	 */
	load(preview, doc) {
		this.preview = preview;
		this.doc = doc;
		this.changed.clear();

		const writable = workflow_allows_edit(this.doctype, doc)
			? (preview.write_permlevels || []).map((permlevel) => cint(permlevel))
			: [];
		this.perm = [];
		for (const level of (preview.permlevels || []).map((permlevel) => cint(permlevel))) {
			this.perm[level] = { permlevel: level, read: 1, write: writable.includes(level) ? 1 : 0 };
		}

		const layout = this.layout;
		layout.doc = doc;
		this.panel.prepare_grids(layout, doc);
		layout.refresh(doc);
		// refresh() rebuilds grid_rows, so the rows to bind only exist now.
		this.panel.make_rows_openable(layout);
	}

	/** The fields that differ from the loaded document, by fieldname. */
	get_changes() {
		/** @type {Record<string, unknown>} */
		const values = {};
		if (!this.preview) return values;
		for (const fieldname of this.changed) {
			const fieldtype = this.layout.fields_dict[fieldname]?.df?.fieldtype;
			const value = this.doc[fieldname];
			if (!same_value(fieldtype, value, this.preview.doc[fieldname])) values[fieldname] = value ?? null;
		}
		return values;
	}

	is_dirty() {
		return Object.keys(this.get_changes()).length > 0;
	}

	discard() {
		this.changed.clear();
	}
}

/**
 * The editor showing the panel's document, if one is: another renderer that wraps the panel (a
 * custom view for some doctype) hides the editors and shows its own view instead.
 * @param {EditableSidePanel} panel
 */
function current_editor(panel) {
	const editor = panel.editor;
	if (!editor?.preview || editor.$wrapper.hasClass("hidden")) return null;
	const { doctype, docname } = panel.current || {};
	return editor.doctype === doctype && editor.preview.doc.name === docname ? editor : null;
}

/**
 * @param {EditableSidePanel} panel
 * @param {Editor} editor
 * @param {() => void} proceed
 */
function confirm_discard(panel, editor, proceed) {
	const name = frappe.utils.escape_html(String(editor.preview?.doc.name ?? ""));
	frappe.warn(
		__("Discard changes?"),
		__("Your changes to {0} {1} are not saved.", [__(editor.doctype), `<strong>${name}</strong>`]),
		() => {
			editor.discard();
			panel.update_editing_state();
			proceed();
		},
		__("Discard"),
	);
}

/**
 * The page changed under the panel, which closes it. When the page is this document's form
 * ("Open in full page", or a link to it), the edits move there, unsaved; otherwise they are gone.
 * @param {Editor} editor
 */
function hand_over_to_form(editor) {
	const values = editor.get_changes();
	if (!editor.preview) return;
	const { name, modified } = editor.preview.doc;
	const [view, doctype, docname] = frappe.get_route() || [];

	if (view !== "Form" || doctype !== editor.doctype || docname !== name) {
		frappe.show_alert({
			message: __("Your changes to {0} {1} were discarded.", [__(editor.doctype), name]),
			indicator: "orange",
		});
		return;
	}

	/** @param {JQuery.TriggeredEvent} _event @param {Form} frm */
	const on_refresh = (_event, frm) => {
		$(document).off("form-refresh", on_refresh);
		if (frm.doctype !== editor.doctype || frm.docname !== name) return;
		if (frm.doc.modified !== modified) {
			frappe.show_alert({
				message: __("{0} {1} was changed since the side panel loaded it; your changes were discarded.", [
					__(editor.doctype),
					name,
				]),
				indicator: "orange",
			});
			return;
		}
		// After the form's own loading calls, so its scripts see the values as typed in.
		frappe.after_ajax(() => frm.set_value(values));
	};
	$(document).on("form-refresh", on_refresh);
}

/**
 * Saves the changed fields and shows the document as the server saved it.
 * @param {EditableSidePanel} panel
 */
async function save(panel) {
	if (panel.saving) return;
	panel.saving = true;
	try {
		// A value still in the focused input lands on blur, and a Link checks it with a request:
		// wait for both, as frappe.app.trigger_primary_action does.
		const active = document.activeElement;
		if (active instanceof HTMLElement && panel.$panel[0]?.contains(active)) active.blur();
		await new Promise((resolve) => setTimeout(resolve, 100));
		await frappe.after_ajax();
		// A validated value is set a few promise ticks after its request settles.
		await new Promise((resolve) => setTimeout(resolve));

		const editor = current_editor(panel);
		const values = editor?.get_changes() || {};
		if (!editor?.preview || !Object.keys(values).length) return;

		const { doctype, name, modified } = editor.preview.doc;
		/** @type {SidePanelPreview} */
		const preview = await frappe.xcall("data_steward.side_panel.save", { doctype, name, values, modified });
		panel.previews[`${doctype}/${name}`] = preview;
		// The panel may have moved on while the request ran.
		if (panel.is_open() && panel.current?.doctype === doctype && panel.current.docname === name) {
			panel.show_preview(doctype, String(name), preview);
		}
		frappe.show_alert({ message: __("Saved"), indicator: "green" });
	} catch {
		// frappe.call has shown the server's message; the edits stay for another try.
	} finally {
		panel.saving = false;
	}
}

/** @param {EditableSidePanel} proto */
function patch(proto) {
	if (proto.__data_steward_editable) return;
	proto.__data_steward_editable = true;

	const { make_buttons, open, back, close } = proto;

	proto.make_buttons = function () {
		make_buttons.call(this);

		this.$save = frappe.ui
			.button({
				label: __("Save"),
				variant: "solid",
				css_class: "side-panel-save hidden",
				onclick: () => save(this),
			})
			.prependTo(this.$panel.find(".side-panel-actions"));
		this.$not_saved = $('<span class="side-panel-not-saved hidden"></span>')
			.append(frappe.ui.badge({ label: __("Not Saved"), theme: "orange" }))
			.insertAfter(this.$panel.find(".side-panel-indicator"));

		// Ctrl/Cmd+S saves the panel, not the page under it.
		this.$panel.on("keydown", (e) => {
			if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey || e.key.toLowerCase() !== "s") return;
			e.preventDefault();
			e.stopPropagation();
			this.$save?.trigger("click");
		});

		// The form asks before a reload drops its edits, except in developer mode.
		addEventListener(
			"beforeunload",
			(e) => {
				if (frappe.boot.developer_mode || !current_editor(this)?.is_dirty()) return;
				e.preventDefault();
			},
			{ capture: true },
		);
	};

	proto.update_editing_state = function () {
		const editor = current_editor(this);
		const dirty = Boolean(this.is_open() && editor?.is_dirty());
		const submitted = cint(editor?.doc.docstatus) === 1;
		this.$save
			?.toggleClass("hidden", !dirty)
			.find(".es-button__label")
			.text(submitted ? __("Update") : __("Save"));
		this.$not_saved?.toggleClass("hidden", !dirty);
		this.$panel.find(".side-panel-indicator").toggleClass("hidden", dirty);
	};

	proto.render_doc = function (doctype, preview) {
		const doc = structuredClone(preview.doc);
		this.editors ||= {};
		const editor = (this.editors[doctype] ||= new Editor(this, doctype, doc));

		this.$body.find(".side-panel-doc").addClass("hidden");
		editor.$wrapper.removeClass("hidden");
		this.editor = editor;
		editor.load(preview, doc);
		this.update_editing_state();
	};

	proto.open = function (doctype, docname, opts) {
		if (!this.is_open()) this.opened_on = { route: frappe.get_route_str(), path: location.pathname };
		const editor = current_editor(this);
		const same = this.current?.doctype === doctype && this.current.docname === docname;
		if (same || !this.is_open() || !editor?.is_dirty()) return open.call(this, doctype, docname, opts);
		confirm_discard(this, editor, () => open.call(this, doctype, docname, opts));
	};

	proto.back = function () {
		const editor = current_editor(this);
		if (!this.history.length || !editor?.is_dirty()) return back.call(this);
		confirm_discard(this, editor, () => back.call(this));
	};

	// Core closes the panel from its close button, Escape, "Open in full page" (just before it
	// routes) and every route change.
	proto.close = function () {
		const editor = current_editor(this);
		if (!this.is_open() || !editor?.is_dirty()) {
			editor?.discard();
			return close.call(this);
		}

		if (frappe.get_route_str() !== this.opened_on?.route) {
			hand_over_to_form(editor);
			editor.discard();
			return close.call(this);
		}

		// Wait a tick: when a route change is under way the URL has moved by then, and the
		// router's own close() follows once it has parsed the new route.
		setTimeout(() => {
			if (current_editor(this) !== editor || location.pathname !== this.opened_on?.path) return;
			confirm_discard(this, editor, () => close.call(this));
		});
	};
}

// side_panel.bundle.js loads on the first click that opens the panel, and defines the class then:
// patch it as it is assigned, before the panel is built.
if (frappe.ui.SidePanel) {
	patch(/** @type {EditableSidePanel} */ (frappe.ui.SidePanel.prototype));
} else {
	Object.defineProperty(frappe.ui, "SidePanel", {
		configurable: true,
		enumerable: true,
		get: () => undefined,
		set(value) {
			Object.defineProperty(frappe.ui, "SidePanel", {
				configurable: true,
				enumerable: true,
				writable: true,
				value,
			});
			patch(value.prototype);
		},
	});
}
