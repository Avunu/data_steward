# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""Merge duplicate File records into one kept File.

Documents refer to a file by its URL (Attach and Attach Image fields, and
links written into rich text), not by the File record's name, so Frappe's
rename-and-merge, which rewrites Link fields only, is not enough. For each
merged File this:

1. rewrites every spelling of the merged file's URL to the kept file's URL,
   in every Attach and Attach Image field and inside every Text Editor, HTML
   Editor, Markdown Editor, Long Text and Code field, in normal, child and
   Single DocTypes (one query per field, never a document save);
2. moves its attachments to the kept file (`file_storage` for how), and gives
   the other File rows that share its content the kept file's content (with
   cloud_storage, merges them into the kept file as well);
3. deletes the merged File, after pointing every Link and Dynamic Link to it
   at the kept File. Without cloud_storage, a merged File attached to a
   document stays instead, as that document's attachment of the kept file
   (what `File.create_attachment_copy` makes);
4. comments on the kept File.

The merged file's content is removed after the transaction commits, and only
when no File row uses it any more (`file_storage.remove_leftover`), and the
caches Frappe derives from the rewritten documents are cleared. Each merged
File runs in its own savepoint: one that fails is rolled back and reported,
and the others still merge. Nothing here commits; the request does.
"""

import html
import json
import re
from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING, TypedDict, cast
from urllib.parse import quote

import frappe
from frappe import _
from frappe.model.rename_doc import get_link_fields, rename_dynamic_links, update_link_field_values
from frappe.query_builder import Criterion
from frappe.utils import cint, get_url, strip_html
from frappe.utils.html_utils import escape_html

from data_steward.api import assert_capability
from data_steward.data_steward.doctype.data_steward_settings.data_steward_settings import require_roles
from data_steward.data_steward.hooks.file_storage import (
	CONTENT_FIELDS,
	NO_CONTENT,
	RETRIEVE_URL,
	SHARE_URL,
	Fields,
	Leftover,
	content_exists,
	find_copies,
	has_cloud_storage,
	leftover_of,
	move_associations,
	move_sharing_link,
	remove_leftover,
	repoint_copies,
	storage_of,
)

if TYPE_CHECKING:
	from frappe.core.doctype.file.file import File
	from pypika.terms import Term

# Each merged File scans the site's URL fields, so a run is kept small.
MAX_FILES = 100

ATTACH_FIELDTYPES = ("Attach", "Attach Image")
TEXT_FIELDTYPES = ("Text Editor", "HTML Editor", "Markdown Editor", "Long Text", "Code")

# File rows are handled one by one below; Version and Deleted Document are
# records of the past and keep the URL they recorded.
SKIP_DOCTYPES = frozenset(("File", "Version", "Deleted Document"))

# A URL is only replaced where it stands on its own: not right after a
# character that would make it part of a longer path or host, and not right
# before one that would continue it (`/files/a.png` is not `/files/a.png.bak`
# or `/files/a.png-2`; a sentence's closing full stop is fine).
_BEFORE = r"(?<![\w.~%/-])"
_AFTER = r"(?![\w~%/-]|\.\w)"
# The parameter after a private file's `?fid=<name>`, which starts the query
# instead once the `?fid=` is dropped.
_NEXT_PARAMETER = r"(?:&amp;|&)?"

# Characters of the kept file's URL that would end an HTML attribute, a tag or
# a Markdown link early; in text they are written percent-encoded.
_UNSAFE_IN_TEXT = re.compile(r"[\s\"'<>`]")

CLEARED_ON_DELETE = (
	"thumbnail_url",
	"content_hash",
	"attached_to_doctype",
	"attached_to_name",
	"attached_to_field",
)
# cloud_storage's: the key its delete hook would otherwise act on, and the sharing link
CLOUD_STORAGE_FIELDS = ("s3_key", "sharing_link")

STORAGE_LABELS = {
	"local": "on this site",
	"cloud": "in cloud storage",
	"remote": "at an external address",
}


class FileMergeResult(TypedDict):
	file: str
	merged: bool
	references: int
	message: str


@dataclass(frozen=True)
class UrlField:
	"""One Attach or text field of one DocType."""

	doctype: str
	fieldname: str
	is_attach: bool
	issingle: bool
	istable: bool


@dataclass(frozen=True)
class UrlChange:
	"""One URL to replace. A private file's URL may carry `?fid=<File name>`;
	`new_fid` None drops it."""

	old: str
	new: str
	old_fid: str | None = None
	new_fid: str | None = None


@dataclass(frozen=True)
class UrlRewrite:
	"""Every spelling of the URLs being replaced, each mapped to the new URL
	spelled the same way."""

	# what an Attach field's value becomes, exactly
	replacements: dict[str, str]
	pattern: re.Pattern[str]
	# LIKE patterns that every spelling contains one of
	like_patterns: tuple[str, ...]

	def _replace(self, match: re.Match[str]) -> str:
		found, separator = match.group(0), ""
		if found not in self.replacements:
			# a `?fid=` spelling that is dropped, with the parameter after it
			separator = "&amp;" if found.endswith("&amp;") else "&"
			found = found.removesuffix(separator)
		new = self.replacements[found]
		if separator and "?" not in new:
			separator = "?"
		return _UNSAFE_IN_TEXT.sub(lambda char: quote(char.group(0)), new) + separator

	def sub(self, text: str) -> tuple[str, int]:
		"""Replace the URLs in a text field's value, with the new URL's
		characters that are unsafe in HTML or Markdown percent-encoded."""
		return self.pattern.subn(self._replace, text)


@dataclass
class _Outcome:
	references: int = 0
	kept_row: bool = False
	notes: list[str] = field(default_factory=list)
	leftovers: list[Leftover] = field(default_factory=list)
	# (doctype, name) of documents written, for their cache
	touched: set[tuple[str, str]] = field(default_factory=set)


def _like_escape(value: str) -> str:
	return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _quote_key(url: str) -> str:
	"""cloud_storage's URLs with the key itself percent-encoded, slashes too."""
	for prefix in (RETRIEVE_URL, SHARE_URL):
		if url.startswith(prefix):
			return prefix + quote(url.removeprefix(prefix), safe="")
	return url


# The ways a URL is written into a document: as stored, percent-encoded as a
# browser or editor writes a link, percent-encoded as Frappe writes it into an
# attachment comment, HTML-escaped, and with a cloud_storage key encoded whole.
ENCODINGS = (
	lambda url: url,
	lambda url: quote(url, safe="/:?=&"),
	lambda url: quote(url, safe="/:"),
	html.escape,
	_quote_key,
)


def build_url_rewrite(changes: list[UrlChange]) -> UrlRewrite:
	"""The spellings of each change's old URL, relative and absolute on this
	site's URL, with and without the private file's `?fid=`."""
	site = get_url().rstrip("/")
	replacements: dict[str, str] = {}
	# `?fid=` spellings that the new URL drops
	dropped_fid: set[str] = set()
	relative: set[str] = set()
	for change in changes:
		for encode in ENCODINGS:
			old, new = encode(change.old), encode(change.new)
			relative.add(old)
			for prefix in ("", site):
				if change.old_fid:
					spelling = f"{prefix}{old}?fid={change.old_fid}"
					fid = f"?fid={change.new_fid}" if change.new_fid else ""
					replacements.setdefault(spelling, f"{prefix}{new}{fid}")
					if not fid:
						dropped_fid.add(spelling)
				replacements.setdefault(f"{prefix}{old}", f"{prefix}{new}")
	replacements = {old: new for old, new in replacements.items() if old != new}
	# The longest first, so an absolute spelling wins over the relative one inside it.
	alternatives = "|".join(
		re.escape(spelling) + _AFTER + (_NEXT_PARAMETER if spelling in dropped_fid else "")
		for spelling in sorted(replacements, key=len, reverse=True)
	)
	return UrlRewrite(
		replacements=replacements,
		pattern=re.compile(f"{_BEFORE}(?:{alternatives})" if alternatives else r"(?!)"),
		like_patterns=tuple(f"%{_like_escape(spelling)}%" for spelling in sorted(relative)),
	)


def get_url_fields() -> list[UrlField]:
	"""Every Attach, Attach Image and rich-text field of every DocType that has
	a table (or is a Single), standard, custom or retyped by a Property Setter."""
	fieldtypes = (*ATTACH_FIELDTYPES, *TEXT_FIELDTYPES)
	doctypes = set(
		frappe.get_all(
			"DocField",
			filters={"fieldtype": ("in", fieldtypes), "parenttype": "DocType"},
			pluck="parent",
			distinct=True,
		)
	)
	doctypes.update(
		frappe.get_all("Custom Field", filters={"fieldtype": ("in", fieldtypes)}, pluck="dt", distinct=True)
	)
	doctypes.update(
		frappe.get_all(
			"Property Setter",
			filters={"property": "fieldtype", "value": ("in", fieldtypes)},
			pluck="doc_type",
			distinct=True,
		)
	)

	url_fields: list[UrlField] = []
	for doctype in sorted(doctypes - SKIP_DOCTYPES):
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		if meta.is_virtual or (not meta.issingle and not frappe.db.table_exists(doctype)):
			continue
		for df in meta.fields:
			if df.fieldtype not in fieldtypes or df.is_virtual:
				continue
			if not meta.issingle and not frappe.db.has_column(doctype, df.fieldname):
				continue
			url_fields.append(
				UrlField(
					doctype=doctype,
					fieldname=cast(str, df.fieldname),
					is_attach=df.fieldtype in ATTACH_FIELDTYPES,
					issingle=bool(meta.issingle),
					istable=bool(meta.istable),
				)
			)
	return url_fields


def _table_condition(url_field: UrlField, rewrite: UrlRewrite) -> Term:
	column = frappe.qb.DocType(url_field.doctype)[url_field.fieldname]
	if url_field.is_attach:
		return column.isin(list(rewrite.replacements))
	return Criterion.any([column.like(pattern) for pattern in rewrite.like_patterns])


def _single_rows(single_fields: list[UrlField], rewrite: UrlRewrite) -> list[frappe._dict]:
	if not single_fields:
		return []
	keys = {(f.doctype, f.fieldname) for f in single_fields}
	singles = frappe.qb.DocType("Singles")
	candidates = [singles.value.isin(list(rewrite.replacements))]
	candidates += [singles.value.like(pattern) for pattern in rewrite.like_patterns]
	rows = (
		frappe.qb.from_(singles)
		.select(singles.doctype, singles.field, singles.value)
		.where(singles.doctype.isin(sorted({f.doctype for f in single_fields})))
		.where(Criterion.any(candidates))
		.run(as_dict=True)
	)
	return [row for row in rows if (row.doctype, row.field) in keys]


def fields_with_matches(url_fields: list[UrlField], rewrite: UrlRewrite) -> list[UrlField]:
	"""The fields that hold any of the URLs at all: one query per field for the
	whole run, so each merged File only reads the few fields that matter."""
	if not rewrite.replacements:
		return []
	matching: list[UrlField] = []
	for url_field in url_fields:
		if url_field.issingle:
			continue
		table = frappe.qb.DocType(url_field.doctype)
		if (
			frappe.qb.from_(table)
			.select(table.name)
			.where(_table_condition(url_field, rewrite))
			.limit(1)
			.run()
		):
			matching.append(url_field)
	single_rows = _single_rows([f for f in url_fields if f.issingle], rewrite)
	single_keys = {(row.doctype, row.field) for row in single_rows}
	matching += [f for f in url_fields if f.issingle and (f.doctype, f.fieldname) in single_keys]
	return matching


def _rewrite_table_field(url_field: UrlField, rewrite: UrlRewrite, outcome: _Outcome) -> None:
	table = frappe.qb.DocType(url_field.doctype)
	columns = [table.name, table[url_field.fieldname].as_("value")]
	if url_field.istable:
		columns += [table.parent, table.parenttype]
	rows = (
		frappe.qb.from_(table).select(*columns).where(_table_condition(url_field, rewrite)).run(as_dict=True)
	)

	updates: dict[str, dict[str, str]] = {}
	for row in rows:
		if url_field.is_attach:
			# MariaDB's IN also matches another case or trailing spaces
			new = rewrite.replacements.get(row.value)
			if new is None:
				continue
			updates[row.name] = {url_field.fieldname: new}
		else:
			text, count = rewrite.sub(row.value)
			if not count:
				continue
			updates[row.name] = {url_field.fieldname: text}
		if url_field.istable:
			outcome.touched.add((row.parenttype, row.parent))
		else:
			outcome.touched.add((url_field.doctype, row.name))
	if updates:
		frappe.db.bulk_update(url_field.doctype, updates, update_modified=False)
		outcome.references += len(updates)


def _rewrite_single_fields(single_fields: list[UrlField], rewrite: UrlRewrite, outcome: _Outcome) -> None:
	attach = {(f.doctype, f.fieldname) for f in single_fields if f.is_attach}
	for row in _single_rows(single_fields, rewrite):
		if (row.doctype, row.field) in attach:
			value = rewrite.replacements.get(row.value)
			if value is None:
				continue
		else:
			value, count = rewrite.sub(cast(str, row.value))
			if not count:
				continue
		doctype = cast(str, row.doctype)
		frappe.db.set_single_value(doctype, row.field, value, update_modified=False)
		outcome.touched.add((doctype, doctype))
		outcome.references += 1


def rewrite_urls(url_fields: list[UrlField], rewrite: UrlRewrite, outcome: _Outcome) -> None:
	if not rewrite.replacements:
		return
	for url_field in url_fields:
		if not url_field.issingle:
			_rewrite_table_field(url_field, rewrite, outcome)
	_rewrite_single_fields([f for f in url_fields if f.issingle], rewrite, outcome)


def rewrite_links(old: str, new: str, outcome: _Outcome) -> None:
	"""Link fields to the merged File, and Dynamic Links to it (comments,
	shares, versions), now name the kept one. Frappe's own rename helpers."""
	link_fields = get_link_fields("File")
	for link_field in link_fields:
		if link_field["issingle"]:
			if frappe.db.get_single_value(link_field["parent"], link_field["fieldname"]) == old:
				outcome.references += 1
		else:
			outcome.references += frappe.db.count(link_field["parent"], {link_field["fieldname"]: old})
	update_link_field_values(link_fields, old, new, "File")
	rename_dynamic_links("File", old, new)


def keeps_its_row(merged: File, kept: File) -> bool:
	"""Without cloud_storage, a merged File attached to a document stays as
	that document's attachment of the kept file, unless the document is gone
	or already has the kept file."""
	doctype, name = merged.attached_to_doctype, merged.attached_to_name
	if not (doctype and name and frappe.db.exists("DocType", doctype) and frappe.db.exists(doctype, name)):
		return False
	urls = frappe.get_all(
		"File",
		filters={
			"name": ("!=", merged.name),
			"attached_to_doctype": doctype,
			"attached_to_name": name,
			"file_url": kept.file_url,
		},
		pluck="file_url",
	)
	# MariaDB's comparison ignores case: `/files/Logo.png` is another file
	return kept.file_url not in urls


def delete_merged_row(merged: File) -> None:
	"""Delete the merged File without letting its `on_trash` remove any
	content: Frappe's removes it when no other row has the same content hash,
	and cloud_storage's removes whatever `file_url` names, even when the kept
	file uses it. With the URL, hash and attachment cleared there is nothing
	for either to act on; `remove_leftover` cleans up after the commit."""
	meta = frappe.get_meta("File")
	cleared: dict[str, str | None] = {"file_url": ""}
	for fieldname in (*CLEARED_ON_DELETE, *CLOUD_STORAGE_FIELDS):
		if meta.has_field(fieldname):
			cleared[fieldname] = None
	frappe.db.set_value("File", merged.name, cleared, update_modified=False)
	# delete permission was checked before anything changed
	frappe.delete_doc("File", merged.name, ignore_permissions=True)


def _storage_mismatch(merged: File, kept: File) -> str | None:
	merged_storage, kept_storage = storage_of(merged), storage_of(kept)
	if merged_storage in (kept_storage, NO_CONTENT):
		return None
	return _("{0} is stored {1} and {2} {3}. Files stored in different places cannot be merged.").format(
		merged.name,
		_(STORAGE_LABELS[merged_storage]),
		kept.name,
		_(STORAGE_LABELS[kept_storage]),
	)


def load_merged(kept: File, name: str) -> File:
	if name == kept.name:
		frappe.throw(_("A file cannot be merged into itself."))
	if not frappe.db.exists("File", name):
		frappe.throw(_("File {0} does not exist.").format(name), frappe.DoesNotExistError)
	merged = cast("File", frappe.get_doc("File", name))
	if merged.is_folder:
		frappe.throw(_("{0} is a folder. Only files can be merged.").format(name))
	if cint(merged.is_private) != cint(kept.is_private):
		frappe.throw(
			_("{0} and {1} are not both private or both public, so they cannot be merged.").format(
				name, kept.name
			)
		)
	mismatch = _storage_mismatch(merged, kept)
	if mismatch:
		frappe.throw(mismatch)
	merged.check_permission("delete")
	return merged


def _move_cloud_storage_records(merged: File, kept: File, outcome: _Outcome) -> list[UrlChange]:
	"""cloud_storage's attachments and sharing link; the share URL to rewrite, if any."""
	attached = move_associations(merged, kept)
	if attached:
		outcome.notes.append(_("Its attachments to {0} document(s) now show the kept file.").format(attached))
	versions = len(merged.get("versions") or [])
	if versions:
		outcome.notes.append(_("Its version history ({0}) was not carried over.").format(versions))
	moved = move_sharing_link(merged, kept)
	if moved:
		outcome.notes.append(_("Its sharing link now shares the kept file."))
	elif moved is False:
		outcome.notes.append(
			_("Its sharing link no longer works; links to it on this site now use the kept file's.")
		)
		return [UrlChange(SHARE_URL + merged.get("sharing_link"), SHARE_URL + kept.get("sharing_link"))]
	return []


def _url_changes(file: Fields, kept: File) -> list[UrlChange]:
	"""A File row's URL, and its `?fid=`, to replace with the kept file's URL
	when the row is deleted."""
	if not file.get("file_url"):
		return []
	return [
		UrlChange(
			file.get("file_url"),
			kept.file_url or "",
			old_fid=file.get("name") if cint(file.get("is_private")) else None,
		)
	]


def _fold_copy_records(copies: list[File], kept: File, outcome: _Outcome) -> list[UrlChange]:
	"""cloud_storage: the copies' attachments and sharing links go to the kept
	File, as the merged File's do; the URLs to rewrite."""
	changes: list[UrlChange] = []
	attached = 0
	for copy in copies:
		attached += move_associations(copy, kept)
		changes += _url_changes(copy, kept)
		if move_sharing_link(copy, kept) is False:
			changes.append(
				UrlChange(SHARE_URL + copy.get("sharing_link"), SHARE_URL + kept.get("sharing_link"))
			)
	notes = [
		_("{0} other File record(s) that used its content were merged into the kept file too.").format(
			len(copies)
		)
	]
	if attached:
		notes.append(_("Their attachments to {0} document(s) now show the kept file.").format(attached))
	outcome.notes += notes
	return changes


def _merge_one(
	kept: File, name: str, url_fields: list[UrlField], cloud: bool, run: frozenset[str], outcome: _Outcome
) -> None:
	merged = load_merged(kept, name)
	keep = cast(str, kept.name)
	outcome.leftovers.append(leftover_of(merged))
	outcome.kept_row = not cloud and keeps_its_row(merged, kept)
	# a copy that is merged in this run gets its own turn
	copies = find_copies(merged, exclude={*run, name, keep})

	changes: list[UrlChange] = []
	if merged.file_url:
		changes.append(
			UrlChange(
				merged.file_url,
				kept.file_url or "",
				old_fid=name if cint(merged.is_private) else None,
				# a deleted row's fid would find nothing; without one, any row
				# for the URL the user can read lets the file through
				new_fid=name if outcome.kept_row else None,
			)
		)
	folded: list[File] = []
	if cloud:
		changes += _move_cloud_storage_records(merged, kept, outcome)
		# cloud_storage's delete hook removes the content a row names, whoever
		# else uses it, so no row is left sharing the kept file's content
		folded = [cast("File", frappe.get_doc("File", row.name)) for row in copies]
		if folded:
			changes += _fold_copy_records(folded, kept, outcome)
	rewrite_urls(url_fields, build_url_rewrite(changes), outcome)

	for copy in folded:
		outcome.leftovers.append(leftover_of(copy))
		outcome.touched.add(("File", cast(str, copy.name)))
		rewrite_links(cast(str, copy.name), keep, outcome)
		delete_merged_row(copy)
	if copies and not cloud:
		repoint_copies([row.name for row in copies], kept)
		outcome.touched.update(("File", row.name) for row in copies)
		outcome.notes.append(
			_("{0} other File record(s) that used its content now use the kept file's.").format(len(copies))
		)

	themes = sorted(theme for doctype, theme in outcome.touched if doctype == "Website Theme")
	if themes:
		outcome.notes.append(
			_("Save Website Theme {0} to rebuild its style sheet with the kept file.").format(
				", ".join(themes)
			)
		)

	if outcome.kept_row:
		frappe.db.set_value("File", name, {f: kept.get(f) for f in CONTENT_FIELDS})
		outcome.notes.insert(
			0,
			_("Kept as the attachment of {0} {1}, now showing the kept file.").format(
				merged.attached_to_doctype, merged.attached_to_name
			),
		)
	else:
		rewrite_links(name, keep, outcome)
		delete_merged_row(merged)
		outcome.notes.insert(0, _("Deleted."))

	label = f"{merged.file_name or name} ({name}, {merged.file_url or ''})"
	kept.add_comment(
		"Edit",
		escape_html(
			" ".join(
				[
					_("Merged {0} into this file. References changed to this file: {1}.").format(
						label, outcome.references
					),
					*outcome.notes,
				]
			)
		),
	)


def _clear_caches(touched: set[tuple[str, str]]) -> None:
	for doctype, name in touched:
		frappe.clear_document_cache(doctype, name)


def clear_derived_caches() -> None:
	"""After the commit: what Frappe builds from documents and keeps, which
	the rewrites, made without saving, do not reach: every user's desk boot
	info (the app logo is in it) and the website's cached pages."""
	from frappe.website.utils import clear_cache

	cache = frappe.cache
	# a site always has its cache; the check is for the type checker
	if cache:
		cache.delete_key("bootinfo")
	clear_cache()


def merge_one_in_savepoint(
	kept: File, name: str, url_fields: list[UrlField], cloud: bool, run: frozenset[str] = frozenset()
) -> FileMergeResult:
	savepoint = f"ds_file_merge_{frappe.generate_hash(length=10)}"
	messages = len(frappe.local.message_log)
	outcome = _Outcome()
	outcome.touched.update({("File", cast(str, kept.name)), ("File", name)})
	frappe.db.savepoint(savepoint)
	try:
		_merge_one(kept, name, url_fields, cloud, run, outcome)
	except Exception as exc:
		frappe.db.rollback(save_point=savepoint)
		_clear_caches(outcome.touched)
		# with cloud_storage the kept File may have taken an attachment or a sharing link in memory
		kept.reload()
		# The log line reports it; the desk need not also pop it up.
		frappe.local.message_log[messages:] = []
		return {
			"file": name,
			"merged": False,
			"references": 0,
			"message": strip_html(str(exc)) or type(exc).__name__,
		}
	frappe.db.release_savepoint(savepoint)
	_clear_caches(outcome.touched)
	for leftover in outcome.leftovers:
		frappe.db.after_commit.add(partial(remove_leftover, leftover))
	return {
		"file": name,
		"merged": True,
		"references": outcome.references,
		"message": " ".join(outcome.notes),
	}


def get_kept_file(keep: str) -> File:
	if not frappe.db.exists("File", keep):
		frappe.throw(_("File {0} does not exist.").format(keep), frappe.DoesNotExistError)
	kept = cast("File", frappe.get_doc("File", keep))
	if kept.is_folder or not kept.file_url:
		frappe.throw(_("{0} is not a file, so nothing can be merged into it.").format(keep))
	kept.check_permission("write")
	if not content_exists(kept):
		frappe.throw(
			_("The content of {0} ({1}) is missing, so nothing can be merged into it.").format(
				keep, kept.file_url
			)
		)
	return kept


def parse_file_names(files: str | list[str]) -> list[str]:
	names = json.loads(files) if isinstance(files, str) else files
	if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
		frappe.throw(_("Files to merge must be a list of File names."))
	names = list(dict.fromkeys(name for name in names if name))
	if not names:
		frappe.throw(_("Select at least one file to merge."))
	if len(names) > MAX_FILES:
		frappe.throw(_("At most {0} files can be merged at once.").format(MAX_FILES))
	return names


def _scan_changes(kept: File, names: list[str], cloud: bool = False) -> list[UrlChange]:
	"""Every URL the run may replace, to find the fields that hold any of them."""
	fields = ["name", "file_url", "is_private"]
	meta = frappe.get_meta("File")
	fields += [fieldname for fieldname in ("sharing_link", "s3_key") if meta.has_field(fieldname)]
	changes: list[UrlChange] = []
	rows = frappe.get_all("File", filters={"name": ("in", names)}, fields=fields)
	if cloud:
		exclude = {*names, cast(str, kept.name)}
		rows = [*rows, *(copy for row in rows for copy in find_copies(row, exclude=exclude))]
	for row in rows:
		changes += _url_changes(row, kept)
		if row.get("sharing_link"):
			changes.append(UrlChange(SHARE_URL + row.sharing_link, kept.file_url or ""))
	return changes


@frappe.whitelist(methods=["POST"])
def merge_files(keep: str, files: str | list[str]) -> list[FileMergeResult]:
	"""Merge each File in `files` into the File `keep`.

	Returns one result per file, merged or not. System Manager only, with write
	permission on the kept File and delete permission on each merged one.
	"""
	assert_capability("file_merge")
	require_roles("System Manager")
	names = parse_file_names(files)
	kept = get_kept_file(keep)
	cloud = has_cloud_storage()
	url_fields = fields_with_matches(get_url_fields(), build_url_rewrite(_scan_changes(kept, names, cloud)))
	run = frozenset(names)
	results = [merge_one_in_savepoint(kept, name, url_fields, cloud, run) for name in names]
	if any(result["merged"] for result in results):
		frappe.db.after_commit.add(clear_derived_caches)
	return results
