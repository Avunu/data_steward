# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""Where a File's content lives, and removing it once nothing uses it.

Plain Frappe keeps a file under the site's `public/files` or `private/files`,
and File rows with the same content share one `file_url`. When a site has the
cloud_storage app (agritheory/cloud_storage), three more things hold, and this
module is where the file merge asks about them:

- content in S3 has the URL `/api/method/retrieve?key=<key>`, with the key in
  the File's `s3_key`;
- one File row stands for every document its content is attached to, through
  its `file_association` rows, and the desk lists a document's attachments from
  those rows, not from `attached_to_*`;
- its `delete_file_data_content` hook deletes the S3 object named in `file_url`
  without asking whether another File row uses it, and ignores
  `only_thumbnail`; with `use_local` it deletes the local file the same way.

data_steward does not depend on cloud_storage: everything here asks first.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, cast

import frappe
from frappe import _
from frappe.utils import now_datetime

if TYPE_CHECKING:
	from frappe.core.doctype.file.file import File

LOCAL = "local"
CLOUD = "cloud"
REMOTE = "remote"
NO_CONTENT = "none"

RETRIEVE_URL = "/api/method/retrieve?key="
SHARE_URL = "/api/method/share?key="
LOCAL_PREFIXES = ("/files/", "/private/files/")

ASSOCIATION = "File Association"

# What a File row carries of its content; an attachment of the kept file takes these from it.
CONTENT_FIELDS = ("file_name", "file_url", "content_hash", "file_size", "file_type", "thumbnail_url")


class Fields(Protocol):
	"""A File document, or a row of File values."""

	def get(self, key: str, /) -> Any: ...


def has_cloud_storage() -> bool:
	"""cloud_storage is installed on this site and has added its File fields."""
	return "cloud_storage" in frappe.get_installed_apps() and bool(
		frappe.get_meta("File").has_field("file_association")
	)


def cloud_storage_on() -> bool:
	"""Files are written to S3: cloud_storage is installed and configured, without `use_local`."""
	settings = frappe.conf.get("cloud_storage_settings")
	return bool(settings and not settings.get("use_local") and has_cloud_storage())


def content_fields() -> tuple[str, ...]:
	return (*CONTENT_FIELDS, "s3_key") if has_cloud_storage() else CONTENT_FIELDS


def storage_of(file: Fields) -> str:
	"""Where the File's content is: on this site's disk, in cloud_storage's
	S3 bucket, at another address, or nowhere (a row with no URL)."""
	url = file.get("file_url") or ""
	if file.get("s3_key") or url.startswith(RETRIEVE_URL):
		return CLOUD
	if url.startswith(LOCAL_PREFIXES):
		return LOCAL
	return REMOTE if url else NO_CONTENT


def cloud_keys(file: Fields) -> frozenset[str]:
	"""The S3 keys a File names: its `s3_key` and the key in its retrieve URL.
	cloud_storage reads the first to serve the file and deletes the second."""
	keys = {file.get("s3_key") or ""}
	url = file.get("file_url") or ""
	if url.startswith(RETRIEVE_URL):
		keys.add(url.removeprefix(RETRIEVE_URL))
	return frozenset(key for key in keys if key)


def cloud_client() -> Any:
	"""cloud_storage's own S3 client, with its bucket on `.bucket`."""
	return frappe.get_attr("cloud_storage.cloud_storage.overrides.file.get_cloud_storage_client")()


def _missing_object(exc: Exception) -> bool:
	error = getattr(exc, "response", None) or {}
	return str(error.get("Error", {}).get("Code")) in ("404", "NoSuchKey", "NotFound")


def content_exists(file: File) -> bool:
	"""Whether the kept file's content is really there. A file at another
	address cannot be checked from here and counts as there."""
	storage = storage_of(file)
	if storage == LOCAL:
		return bool(file.exists_on_disk())
	if storage != CLOUD:
		return True
	if not cloud_storage_on():
		frappe.throw(
			_("{0} is kept in cloud storage, which is not set up on this site.").format(file.name),
			title=_("Cloud storage not configured"),
		)
	key = file.get("s3_key") or next(iter(cloud_keys(file)), "")
	client = cloud_client()
	try:
		client.head_object(Bucket=client.bucket, Key=key)
	except Exception as exc:
		if _missing_object(exc):
			return False
		raise
	return True


def _associations(parent: str) -> list[Any]:
	return frappe.get_all(
		ASSOCIATION,
		filters={"parent": parent, "parenttype": "File"},
		fields=["name", "link_doctype", "link_name", "idx"],
		order_by="idx asc",
	)


def _add_association(parent: str, link: tuple[str, str], idx: int) -> None:
	frappe.get_doc(
		{
			"doctype": ASSOCIATION,
			"parent": parent,
			"parenttype": "File",
			"parentfield": "file_association",
			"idx": idx,
			"link_doctype": link[0],
			"link_name": link[1],
			"user": frappe.session.user,
			"timestamp": now_datetime(),
		}
	).db_insert()


def _reparent_association(name: str, parent: str, idx: int) -> None:
	frappe.db.set_value(ASSOCIATION, name, {"parent": parent, "idx": idx}, update_modified=False)


def _drop_association(name: str) -> None:
	frappe.db.delete(ASSOCIATION, {"name": name})


def _document_exists(doctype: str | None, name: str | None) -> bool:
	return bool(doctype and name and frappe.db.exists("DocType", doctype) and frappe.db.exists(doctype, name))


def move_associations(merged: File, kept: File) -> int:
	"""cloud_storage: every document the merged File is attached to gets the
	kept File instead. Its `file_association` rows move to the kept File, except
	for a document the kept File is already attached to; a merged File attached
	from before cloud_storage was installed, with no row, gets one on the kept
	File. When the kept File was attached to nothing, its `attached_to_*` names
	the first document, as cloud_storage's own uploads do. Returns how many
	documents now have the kept File."""
	kept_name, merged_name = cast(str, kept.name), cast(str, merged.name)
	kept_rows = _associations(kept_name)
	linked = {(row.link_doctype, row.link_name) for row in kept_rows}
	idx = max((row.idx or 0 for row in kept_rows), default=0)
	added: list[tuple[str, str]] = []
	for row in _associations(merged_name):
		link = (row.link_doctype, row.link_name)
		if link in linked:
			_drop_association(row.name)
			continue
		idx += 1
		_reparent_association(row.name, kept_name, idx)
		linked.add(link)
		added.append(link)

	own = (merged.attached_to_doctype or "", merged.attached_to_name or "")
	if own not in linked and _document_exists(*own):
		idx += 1
		_add_association(kept_name, own, idx)
		added.append(own)

	if added and not kept.attached_to_doctype:
		kept.attached_to_doctype, kept.attached_to_name = added[0]
		frappe.db.set_value(
			"File",
			kept_name,
			{"attached_to_doctype": added[0][0], "attached_to_name": added[0][1]},
			update_modified=False,
		)
	return len(added)


def move_sharing_link(merged: File, kept: File) -> bool | None:
	"""cloud_storage's sharing link (`/api/method/share?key=<link>`), which
	people outside the site may hold. The merged File's link moves to the kept
	File when that has none, so it keeps working and shares the kept file:
	True. When both have one, the merged File's link stops working: False.
	None when the merged File has no link."""
	link = merged.get("sharing_link")
	if not link:
		return None
	if kept.get("sharing_link"):
		return False
	frappe.db.set_value("File", merged.name, "sharing_link", None, update_modified=False)
	frappe.db.set_value("File", kept.name, "sharing_link", link, update_modified=False)
	kept.set("sharing_link", link)
	return True


def repoint_copies(merged: File, kept: File) -> int:
	"""Other File rows that use the merged File's content (Frappe's attachment
	copies share its `file_url`; cloud_storage's may share its `s3_key`) take the
	kept File's content, so none of them keeps the merged content alive or shows
	it any longer. Returns how many rows changed."""
	or_filters: dict[str, Any] = {}
	if merged.file_url:
		or_filters["file_url"] = merged.file_url
	keys = cloud_keys(merged)
	if keys and has_cloud_storage():
		or_filters["s3_key"] = ("in", sorted(keys))
	if not or_filters:
		return 0
	copies = frappe.get_all(
		"File",
		filters={"name": ("not in", (merged.name, kept.name)), "is_folder": 0},
		or_filters=or_filters,
		pluck="name",
	)
	values = {fieldname: kept.get(fieldname) for fieldname in content_fields()}
	for name in copies:
		frappe.db.set_value("File", name, values)
	return len(copies)


@dataclass(frozen=True)
class Leftover:
	"""The content a merged File used, removed after the commit when no File row uses it any more."""

	file_url: str | None = None
	thumbnail_url: str | None = None
	keys: frozenset[str] = frozenset()


def leftover_of(file: Fields) -> Leftover:
	return Leftover(
		file_url=file.get("file_url") or None,
		thumbnail_url=file.get("thumbnail_url") or None,
		keys=cloud_keys(file) if storage_of(file) == CLOUD else frozenset(),
	)


def _url_in_use(url: str) -> bool:
	return bool(
		frappe.db.exists("File", {"file_url": url}) or frappe.db.exists("File", {"thumbnail_url": url})
	)


def _key_in_use(key: str) -> bool:
	return bool(
		frappe.db.exists("File", {"s3_key": key}) or frappe.db.exists("File", {"file_url": RETRIEVE_URL + key})
	)


def _deletable_local_url(url: str | None) -> bool:
	"""Frappe's `delete_file` only resolves `/files/<name>` and
	`/private/files/<name>`: for a URL in a sub-folder it would remove a file
	of the same name at the top, so such a URL is left alone."""
	for prefix in LOCAL_PREFIXES:
		if url and url.startswith(prefix):
			return "/" not in url.removeprefix(prefix)
	return False


def _remove_local(leftover: Leftover) -> None:
	file_url = leftover.file_url
	thumbnail_url = leftover.thumbnail_url
	if not (_deletable_local_url(file_url) and not _url_in_use(file_url or "")):
		file_url = None
	if not (_deletable_local_url(thumbnail_url) and not _url_in_use(thumbnail_url or "")):
		thumbnail_url = None
	if not (file_url or thumbnail_url):
		return
	# Frappe's own removal from the site's files, which every storage hook falls
	# back on for a local file. Only what no row uses is set on this stand-in.
	gone = cast("File", frappe.new_doc("File"))
	gone.file_url = file_url
	gone.thumbnail_url = thumbnail_url
	gone.delete_file_from_filesystem(only_thumbnail=not file_url)


def _remove_cloud(keys: frozenset[str]) -> None:
	"""cloud_storage's S3 objects, through its own client. Its delete hook is
	not used: it deletes whatever `file_url` names, used or not."""
	unused = sorted(key for key in keys if not _key_in_use(key))
	if not unused:
		return
	client = cloud_client()
	for key in unused:
		client.delete_object(Bucket=client.bucket, Key=key)


def remove_leftover(leftover: Leftover) -> None:
	"""After the commit: remove the merged file's content and thumbnail where
	no File row uses them any more. A failure is logged; the merge stands."""
	try:
		# A retrieve URL is never a local one, so for a cloud file only the thumbnail is.
		_remove_cloud(leftover.keys)
		_remove_local(leftover)
	except Exception:
		frappe.log_error(title=_("File merge: removing a merged file's content failed"))
