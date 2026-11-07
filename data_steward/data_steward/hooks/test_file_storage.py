# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""`hooks.file_storage`: the file merge on a site with the cloud_storage app.

CI's site does not have cloud_storage, so its pieces are faked here: the
`File Association` rows are an in-memory table behind the four functions that
read and write them (each checked on its own against the queries it sends),
and the S3 client is a mock. The real app is only exercised on a bench that
has it, against a local S3-compatible server such as moto's.
"""

from __future__ import annotations

import os
from contextlib import ExitStack, contextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import frappe

from data_steward.data_steward.hooks import file as file_merge
from data_steward.data_steward.hooks import file_storage
from data_steward.data_steward.hooks.file import (
	UrlChange,
	_fold_copy_records,
	_move_cloud_storage_records,
	_Outcome,
	_scan_changes,
	merge_files,
)
from data_steward.data_steward.hooks.file_storage import (
	ASSOCIATION,
	CLOUD,
	CONTENT_FIELDS,
	LOCAL,
	NO_CONTENT,
	REMOTE,
	RETRIEVE_URL,
	Leftover,
	cloud_keys,
	content_exists,
	content_fields,
	find_copies,
	leftover_of,
	move_associations,
	move_sharing_link,
	remove_leftover,
	repoint_copies,
	storage_of,
)
from data_steward.tests import DataStewardIntegrationTestCase
from data_steward.tests.factories import make_file

if TYPE_CHECKING:
	from collections.abc import Generator

	from frappe.core.doctype.file.file import File

S3_SETTINGS = {
	"access_key": "test",
	"secret": "test",
	"region": "us-east-1",
	"bucket": "test",
	"endpoint_url": "http://127.0.0.1:1",
}
TIMESTAMP = datetime(2026, 1, 15, 12, 0)


def _file(**fields: Any) -> File:
	"""An unsaved File carrying cloud_storage's fields as plain attributes."""
	doc = cast("File", frappe.new_doc("File"))
	for fieldname, value in fields.items():
		setattr(doc, fieldname, value)
	return doc


def _todo() -> Any:
	return frappe.get_doc({"doctype": "ToDo", "description": "_DS Test cloud"}).insert(
		ignore_permissions=True
	)


def _in_text(url: str) -> str:
	"""A URL as the merge writes it into a text field: spaces percent-encoded."""
	return url.replace(" ", "%20")


class _S3Error(Exception):
	def __init__(self, code: str) -> None:
		super().__init__(code)
		self.response = {"Error": {"Code": code}}


class FakeAssociations:
	"""`File Association` rows, in memory: parent -> [(row name, link_doctype, link_name)]."""

	def __init__(self, rows: dict[str, list[tuple[str, str]]]) -> None:
		self.rows: dict[str, list[frappe._dict]] = {}
		for parent, links in rows.items():
			for link in links:
				self.add(parent, link, len(self.rows.get(parent, [])) + 1)

	def add(self, parent: str, link: tuple[str, str], idx: int) -> None:
		name = frappe.generate_hash(length=10)
		row = frappe._dict(name=name, link_doctype=link[0], link_name=link[1], idx=idx)
		self.rows.setdefault(parent, []).append(row)

	def get(self, parent: str) -> list[frappe._dict]:
		return sorted(self.rows.get(parent, []), key=lambda row: cast(int, row.idx))

	def _pop(self, name: str) -> frappe._dict:
		for rows in self.rows.values():
			for row in rows:
				if row.name == name:
					rows.remove(row)
					return row
		raise AssertionError(name)

	def reparent(self, name: str, parent: str, idx: int) -> None:
		row = self._pop(name)
		row.idx = idx
		self.rows.setdefault(parent, []).append(row)

	def drop(self, name: str) -> None:
		self._pop(name)

	def links(self, parent: str) -> list[tuple[str, str]]:
		return [(cast(str, row.link_doctype), cast(str, row.link_name)) for row in self.get(parent)]

	@contextmanager
	def installed(self) -> Generator[FakeAssociations]:
		with ExitStack() as stack:
			for target, fake in (
				("_associations", self.get),
				("_add_association", self.add),
				("_reparent_association", self.reparent),
				("_drop_association", self.drop),
			):
				stack.enter_context(patch.object(file_storage, target, side_effect=fake))
			yield self


class TestStorage(DataStewardIntegrationTestCase):
	def test_without_cloud_storage(self):
		if "cloud_storage" in frappe.get_installed_apps():
			self.skipTest("cloud_storage is installed on this site")
		self.assertFalse(file_storage.has_cloud_storage())
		with patch.dict(frappe.conf, {"cloud_storage_settings": S3_SETTINGS}):
			self.assertFalse(file_storage.cloud_storage_on())
		self.assertEqual(content_fields(), CONTENT_FIELDS)

	def test_cloud_storage_settings(self):
		with patch.object(file_storage, "has_cloud_storage", return_value=True):
			with patch.dict(frappe.conf, {"cloud_storage_settings": S3_SETTINGS}):
				self.assertTrue(file_storage.cloud_storage_on())
			with patch.dict(frappe.conf, {"cloud_storage_settings": {**S3_SETTINGS, "use_local": 1}}):
				self.assertFalse(file_storage.cloud_storage_on())
			self.assertEqual(content_fields(), (*CONTENT_FIELDS, "s3_key"))

	def test_storage_of(self):
		self.assertEqual(storage_of({"file_url": "/files/a.png"}), LOCAL)
		self.assertEqual(storage_of({"file_url": "/private/files/a.png"}), LOCAL)
		self.assertEqual(storage_of({"file_url": f"{RETRIEVE_URL}f/a.png"}), CLOUD)
		self.assertEqual(storage_of({"file_url": "", "s3_key": "f/a.png"}), CLOUD)
		self.assertEqual(storage_of({"file_url": "https://example.com/a.png"}), REMOTE)
		self.assertEqual(storage_of({"file_url": ""}), NO_CONTENT)

	def test_cloud_keys(self):
		self.assertEqual(
			cloud_keys({"file_url": f"{RETRIEVE_URL}f/a.png", "s3_key": "f/b.png"}),
			frozenset({"f/a.png", "f/b.png"}),
		)
		self.assertEqual(cloud_keys({"file_url": "/files/a.png"}), frozenset())
		self.assertEqual(
			leftover_of({"file_url": f"{RETRIEVE_URL}f/a.png", "thumbnail_url": "/files/t.png"}),
			Leftover(f"{RETRIEVE_URL}f/a.png", "/files/t.png", frozenset({"f/a.png"})),
		)
		self.assertEqual(leftover_of({"file_url": "/files/a.png", "s3_key": ""}).keys, frozenset())


class TestKeptContent(DataStewardIntegrationTestCase):
	def test_an_external_file_counts_as_there(self):
		self.assertTrue(content_exists(_file(file_url="https://example.com/a.png")))

	def test_a_cloud_file_needs_cloud_storage(self):
		with self.assertRaisesRegex(frappe.ValidationError, "not set up on this site"):
			content_exists(_file(name="K", file_url=f"{RETRIEVE_URL}f/a.png"))

	def test_a_cloud_file_is_looked_up_in_the_bucket(self):
		client = MagicMock(bucket="test")
		kept = _file(file_url=f"{RETRIEVE_URL}f/a.png", s3_key="f/a.png")
		with (
			patch.object(file_storage, "cloud_storage_on", return_value=True),
			patch.object(file_storage, "cloud_client", return_value=client),
		):
			self.assertTrue(content_exists(kept))
			client.head_object.assert_called_once_with(Bucket="test", Key="f/a.png")

			client.head_object.side_effect = _S3Error("404")
			self.assertFalse(content_exists(kept))

			client.head_object.side_effect = _S3Error("AccessDenied")
			with self.assertRaises(_S3Error):
				content_exists(kept)

	def test_the_client_is_cloud_storages(self):
		with patch.object(frappe, "get_attr") as get_attr:
			client = file_storage.cloud_client()

		get_attr.assert_called_once_with(
			"cloud_storage.cloud_storage.overrides.file.get_cloud_storage_client"
		)
		self.assertIs(client, get_attr.return_value.return_value)


class TestAssociationQueries(DataStewardIntegrationTestCase):
	"""The four functions that touch `File Association`, against the calls they make."""

	def test_read(self):
		with patch.object(frappe, "get_all", return_value=[]) as get_all:
			file_storage._associations("K")

		get_all.assert_called_once_with(
			ASSOCIATION,
			filters={"parent": "K", "parenttype": "File"},
			fields=["name", "link_doctype", "link_name", "idx"],
			order_by="idx asc",
		)

	def test_add(self):
		# now_datetime reads System Settings through frappe.get_doc when its cache is cold
		with (
			patch.object(frappe, "get_doc") as get_doc,
			patch.object(file_storage, "now_datetime", return_value=TIMESTAMP),
		):
			file_storage._add_association("K", ("ToDo", "T1"), 3)

		row = get_doc.call_args.args[0]
		self.assertEqual(
			{key: row[key] for key in ("doctype", "parent", "parenttype", "parentfield", "idx")},
			{
				"doctype": ASSOCIATION,
				"parent": "K",
				"parenttype": "File",
				"parentfield": "file_association",
				"idx": 3,
			},
		)
		self.assertEqual(
			(row["link_doctype"], row["link_name"], row["user"], row["timestamp"]),
			("ToDo", "T1", "Administrator", TIMESTAMP),
		)
		get_doc.return_value.db_insert.assert_called_once_with()

	def test_reparent_and_drop(self):
		with patch.object(frappe.db, "set_value") as set_value, patch.object(frappe.db, "delete") as delete:
			file_storage._reparent_association("R1", "K", 2)
			file_storage._drop_association("R2")

		set_value.assert_called_once_with(ASSOCIATION, "R1", {"parent": "K", "idx": 2}, update_modified=False)
		delete.assert_called_once_with(ASSOCIATION, {"name": "R2"})


class TestMoveAssociations(DataStewardIntegrationTestCase):
	def test_attachments_move_to_the_kept_file(self):
		a, b, c = _todo(), _todo(), _todo()
		kept = make_file()
		merged = make_file(attached_to_doctype="ToDo", attached_to_name=a.name)
		fake = FakeAssociations(
			{kept.name: [("ToDo", c.name)], merged.name: [("ToDo", b.name), ("ToDo", c.name)]}
		)

		with fake.installed():
			moved = move_associations(merged, kept)

		self.assertEqual(moved, 2)
		self.assertEqual(fake.links(kept.name), [("ToDo", c.name), ("ToDo", b.name), ("ToDo", a.name)])
		self.assertEqual(fake.links(merged.name), [])
		# The kept file was attached to nothing; it now names the first document, as cloud_storage does.
		self.assertEqual((kept.attached_to_doctype, kept.attached_to_name), ("ToDo", b.name))
		self.assertEqual(frappe.db.get_value("File", kept.name, "attached_to_name"), b.name)

	def test_an_attached_kept_file_stays_attached_where_it_was(self):
		a, b = _todo(), _todo()
		kept = make_file(attached_to_doctype="ToDo", attached_to_name=a.name)
		merged = make_file()
		fake = FakeAssociations({kept.name: [("ToDo", a.name)], merged.name: [("ToDo", b.name)]})

		with fake.installed():
			self.assertEqual(move_associations(merged, kept), 1)

		self.assertEqual(kept.attached_to_name, a.name)


class TestSharingLink(DataStewardIntegrationTestCase):
	def test_moves_when_the_kept_file_has_none(self):
		merged, kept = _file(name="M", sharing_link="111"), _file(name="K", sharing_link=None)

		with patch.object(frappe.db, "set_value") as set_value:
			self.assertIs(move_sharing_link(merged, kept), True)

		self.assertEqual(kept.get("sharing_link"), "111")
		set_value.assert_any_call("File", "M", "sharing_link", None, update_modified=False)
		set_value.assert_any_call("File", "K", "sharing_link", "111", update_modified=False)

	def test_is_lost_when_both_have_one(self):
		merged, kept = _file(name="M", sharing_link="111"), _file(name="K", sharing_link="222")

		with patch.object(frappe.db, "set_value") as set_value:
			self.assertIs(move_sharing_link(merged, kept), False)
		set_value.assert_not_called()

	def test_nothing_without_one(self):
		self.assertIsNone(move_sharing_link(_file(name="M"), _file(name="K", sharing_link="222")))


class TestCopies(DataStewardIntegrationTestCase):
	def test_cloud_copies_share_the_url_or_the_key(self):
		merged = _file(name="M", file_url=f"{RETRIEVE_URL}f/a.png", s3_key="f/a.png")
		rows = [
			frappe._dict(name="C1", file_url=f"{RETRIEVE_URL}f/a.png", s3_key=None),
			frappe._dict(name="C2", file_url="/files/a.png", s3_key="f/a.png"),
			# what MariaDB's case-insensitive comparison also returns
			frappe._dict(name="C3", file_url=f"{RETRIEVE_URL}f/A.png", s3_key="f/A.png"),
		]

		with (
			patch.object(file_storage, "has_cloud_storage", return_value=True),
			patch.object(frappe, "get_all", return_value=rows) as get_all,
		):
			copies = find_copies(merged, exclude={"M", "K"})

		self.assertEqual([row.name for row in copies], ["C1", "C2"])
		self.assertEqual(
			get_all.call_args.kwargs["or_filters"],
			{"file_url": f"{RETRIEVE_URL}f/a.png", "s3_key": ("in", ["f/a.png"])},
		)
		self.assertEqual(get_all.call_args.kwargs["filters"]["name"], ("not in", ["K", "M"]))
		self.assertIn("sharing_link", get_all.call_args.kwargs["fields"])

	def test_only_the_exact_url_without_cloud_storage(self):
		merged = make_file(file_name=f"_ds_copy_{frappe.generate_hash(length=8)}.png")
		copy = make_file(file_name="_ds_copy.png")
		frappe.db.set_value("File", copy.name, "file_url", merged.file_url)
		other = make_file(file_name="_ds_other.png")
		frappe.db.set_value("File", other.name, "file_url", merged.file_url.upper())

		copies = find_copies(merged, exclude={merged.name})

		self.assertEqual([row.name for row in copies], [copy.name])

	def test_a_file_without_content_has_no_copies(self):
		self.assertEqual(find_copies(_file(name="M", file_url=""), exclude={"M"}), [])

	def test_copies_take_the_kept_content(self):
		kept = _file(name="K", file_url=f"{RETRIEVE_URL}f/k.png", s3_key="f/k.png", file_name="k.png")

		with (
			patch.object(file_storage, "has_cloud_storage", return_value=True),
			patch.object(frappe.db, "set_value") as set_value,
		):
			self.assertEqual(repoint_copies(["C1"], kept), 1)

		values = set_value.call_args.args[2]
		self.assertEqual(
			(values["file_url"], values["s3_key"], values["file_name"]), (kept.file_url, "f/k.png", "k.png")
		)


class TestRemoveLeftover(DataStewardIntegrationTestCase):
	def test_only_unused_keys_are_deleted(self):
		client = MagicMock(bucket="test")
		leftover = Leftover(file_url=f"{RETRIEVE_URL}f/a.png", keys=frozenset({"f/a.png", "f/used.png"}))

		with (
			patch.object(file_storage, "cloud_client", return_value=client),
			patch.object(file_storage, "_key_in_use", side_effect=lambda key: key == "f/used.png"),
		):
			remove_leftover(leftover)

		client.delete_object.assert_called_once_with(Bucket="test", Key="f/a.png")

	def test_no_client_when_every_key_is_used(self):
		with (
			patch.object(file_storage, "cloud_client") as cloud_client,
			patch.object(file_storage, "_key_in_use", return_value=True),
		):
			remove_leftover(Leftover(keys=frozenset({"f/a.png"})))

		cloud_client.assert_not_called()

	def test_a_key_is_used_by_s3_key_or_retrieve_url(self):
		with patch.object(frappe.db, "exists", side_effect=[None, "F1"]) as exists:
			self.assertTrue(file_storage._key_in_use("f/a.png"))

		exists.assert_any_call("File", {"s3_key": "f/a.png"})
		exists.assert_any_call("File", {"file_url": f"{RETRIEVE_URL}f/a.png"})

	def test_a_file_in_a_sub_folder_is_never_removed(self):
		self.assertFalse(file_storage._deletable_local_url("/files/sub/a.png"))
		self.assertFalse(file_storage._deletable_local_url("https://example.com/files/a.png"))
		self.assertFalse(file_storage._deletable_local_url(None))
		self.assertTrue(file_storage._deletable_local_url("/private/files/a.png"))


class TestMergeWithCloudStorage(DataStewardIntegrationTestCase):
	"""The whole merge, as on a site with cloud_storage keeping files locally (`use_local`)."""

	def test_attached_file_is_folded_into_the_kept_one(self):
		a, b = _todo(), _todo()
		kept = make_file()
		merged = make_file(attached_to_doctype="ToDo", attached_to_name=a.name)
		note = frappe.get_doc({"doctype": "ToDo", "description": f'<img src="{merged.file_url}">'}).insert(
			ignore_permissions=True
		)
		fake = FakeAssociations({merged.name: [("ToDo", a.name), ("ToDo", b.name)]})

		with (
			fake.installed(),
			patch.object(file_merge, "has_cloud_storage", return_value=True),
			self.capability_enabled("file_merge"),
		):
			results = merge_files(kept.name, [merged.name])

		self.assertTrue(results[0]["merged"], results[0]["message"])
		self.assertIn("Its attachments to 2 document(s) now show the kept file.", results[0]["message"])
		# cloud_storage lists attachments from the association rows, so the merged row goes.
		self.assertFalse(frappe.db.exists("File", merged.name))
		self.assertEqual(fake.links(kept.name), [("ToDo", a.name), ("ToDo", b.name)])
		self.assertEqual(
			frappe.db.get_value("ToDo", note.name, "description"), f'<img src="{_in_text(kept.file_url)}">'
		)

	def test_copies_are_folded_into_the_kept_file(self):
		"""With cloud_storage a copy that kept sharing the kept file's content
		could delete it through the app's delete hook, so it is merged too."""
		a, b = _todo(), _todo()
		kept, merged = make_file(), make_file()
		copy = merged.create_attachment_copy("ToDo", b.name, ignore_permissions=True)
		copy.add_comment("Comment", "_DS Test note on the copy")
		note = _todo()
		frappe.db.set_value("ToDo", note.name, "description", f'<img src="{copy.file_url}">')
		path = merged.get_full_path()
		fake = FakeAssociations({merged.name: [("ToDo", a.name)]})

		with (
			fake.installed(),
			patch.object(file_merge, "has_cloud_storage", return_value=True),
			self.capability_enabled("file_merge"),
		):
			results = merge_files(kept.name, [merged.name])
		frappe.db.after_commit.run()

		self.assertTrue(results[0]["merged"], results[0]["message"])
		self.assertIn(
			"1 other File record(s) that used its content were merged into the kept file too.",
			results[0]["message"],
		)
		self.assertIn("Their attachments to 1 document(s) now show the kept file.", results[0]["message"])
		self.assertFalse(frappe.db.exists("File", copy.name))
		self.assertEqual(fake.links(kept.name), [("ToDo", a.name), ("ToDo", b.name)])
		self.assertEqual(
			frappe.db.get_value("ToDo", note.name, "description"), f'<img src="{_in_text(kept.file_url)}">'
		)
		self.assertIn(
			"_DS Test note on the copy",
			frappe.get_all(
				"Comment", filters={"reference_doctype": "File", "reference_name": kept.name}, pluck="content"
			),
		)
		self.assertFalse(os.path.exists(path))

	def test_copies_merged_in_the_same_run_get_their_own_turn(self):
		kept, merged = make_file(), make_file()
		copy = merged.create_attachment_copy("ToDo", _todo().name, ignore_permissions=True)

		with (
			FakeAssociations({}).installed(),
			patch.object(file_merge, "has_cloud_storage", return_value=True),
			self.capability_enabled("file_merge"),
		):
			results = merge_files(kept.name, [merged.name, copy.name])

		self.assertEqual([r["merged"] for r in results], [True, True])
		self.assertNotIn("other File record", results[0]["message"])

	def test_cloud_storage_records_of_the_merged_file(self):
		merged = _file(
			name="M", sharing_link="111", versions=[frappe._dict(version="v1"), frappe._dict(version="v2")]
		)
		kept = _file(name="K", sharing_link="222")
		outcome = _Outcome()

		with patch.object(file_merge, "move_associations", return_value=0):
			changes = _move_cloud_storage_records(merged, kept, outcome)

		self.assertEqual(changes, [UrlChange("/api/method/share?key=111", "/api/method/share?key=222")])
		self.assertEqual(
			outcome.notes,
			[
				"Its version history (2) was not carried over.",
				"Its sharing link no longer works; links to it on this site now use the kept file's.",
			],
		)

	def test_sharing_links_of_folded_copies(self):
		kept = _file(name="K", file_url="/files/k.png")
		first = _file(name="C1", file_url="/files/a.png", is_private=0, sharing_link="111")
		second = _file(name="C2", file_url="/files/a.png", is_private=0, sharing_link="222")
		outcome = _Outcome()

		with (
			patch.object(file_merge, "move_associations", return_value=0),
			patch.object(frappe.db, "set_value"),
		):
			changes = _fold_copy_records([first, second], kept, outcome)

		# The first link moves to the kept file; the second then stops working.
		self.assertEqual(kept.get("sharing_link"), "111")
		self.assertEqual(
			changes,
			[
				UrlChange("/files/a.png", "/files/k.png"),
				UrlChange("/files/a.png", "/files/k.png"),
				UrlChange("/api/method/share?key=222", "/api/method/share?key=111"),
			],
		)
		self.assertEqual(
			outcome.notes,
			["2 other File record(s) that used its content were merged into the kept file too."],
		)

	def test_a_sharing_link_moves_to_a_kept_file_without_one(self):
		merged, kept = _file(name="M", sharing_link="111"), _file(name="K")

		with (
			patch.object(file_merge, "move_associations", return_value=0),
			patch.object(frappe.db, "set_value"),
		):
			self.assertEqual(_move_cloud_storage_records(merged, kept, outcome := _Outcome()), [])

		self.assertEqual(outcome.notes, ["Its sharing link now shares the kept file."])

	def test_sharing_links_are_scanned_for(self):
		rows = [frappe._dict(name="M", file_url="", is_private=0, sharing_link="111")]
		meta = MagicMock()
		meta.has_field.return_value = True

		with (
			patch.object(frappe, "get_meta", return_value=meta),
			patch.object(frappe, "get_all", return_value=rows),
		):
			changes = _scan_changes(_file(name="K", file_url="/files/k.png"), ["M"])

		self.assertEqual(changes, [UrlChange("/api/method/share?key=111", "/files/k.png")])

	def test_cloud_copies_are_scanned_for(self):
		rows = [frappe._dict(name="M", file_url=f"{RETRIEVE_URL}f/a.png", is_private=0)]
		copy = frappe._dict(name="C", file_url="/private/files/a.png", is_private=1, sharing_link="333")

		with (
			patch.object(frappe, "get_all", return_value=rows),
			patch.object(file_merge, "find_copies", return_value=[copy]) as find,
		):
			changes = _scan_changes(_file(name="K", file_url="/files/k.png"), ["M"], cloud=True)

		find.assert_called_once_with(rows[0], exclude={"M", "K"})
		self.assertEqual(
			changes,
			[
				UrlChange(f"{RETRIEVE_URL}f/a.png", "/files/k.png"),
				UrlChange("/private/files/a.png", "/files/k.png", old_fid="C"),
				UrlChange("/api/method/share?key=333", "/files/k.png"),
			],
		)
