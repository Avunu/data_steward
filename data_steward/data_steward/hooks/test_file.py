# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""`hooks.file.merge_files`: merging duplicate File records on a site
without cloud_storage, which is how CI runs. The cloud_storage paths are in
`test_file_storage.py`."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import patch

import frappe
from frappe.desk.form.load import get_attachments
from frappe.tests.classes.context_managers import set_user
from frappe.utils import get_url

from data_steward.data_steward.hooks import file as file_merge
from data_steward.data_steward.hooks.file import (
	MAX_FILES,
	UrlChange,
	_Outcome,
	build_url_rewrite,
	fields_with_matches,
	get_url_fields,
	merge_files,
	parse_file_names,
	rewrite_links,
)
from data_steward.tests import DataStewardIntegrationTestCase
from data_steward.tests.factories import make_file, make_item, make_user, set_capability

if TYPE_CHECKING:
	from frappe.core.doctype.file.file import File


def _commit() -> None:
	"""What the request's commit would run: `remove_leftover` among others."""
	frappe.db.after_commit.run()


def _todo(description: str = "_DS Test file merge") -> Any:
	return frappe.get_doc({"doctype": "ToDo", "description": description}).insert(ignore_permissions=True)


def _in_text(url: str) -> str:
	"""A URL as the merge writes it into a text field: spaces percent-encoded."""
	return url.replace(" ", "%20")


def _attach(content: bytes | None = None, *, to: Any, **fields: Any) -> File:
	return make_file(content, attached_to_doctype=to.doctype, attached_to_name=to.name, **fields)


def _description(name: str) -> str:
	return cast(str, frappe.db.get_value("ToDo", name, "description"))


def _item(item_code: str, **values: str) -> Any:
	"""An Item holding `values` as written, past Frappe's HTML sanitising and
	without the save attaching an Attach field's File to it."""
	item = make_item(item_code)
	frappe.db.set_value("Item", item.name, values)
	return item


class TestBuildUrlRewrite(DataStewardIntegrationTestCase):
	def test_only_whole_urls_are_replaced(self):
		rewrite = build_url_rewrite([UrlChange("/files/a.png", "/files/k.png")])
		site = get_url().rstrip("/")
		text = (
			'<img src="/files/a.png"> /files/a.png.bak /files/a.png-2 /other/files/a.png '
			f"x/files/a.png See /files/a.png. ({site}/files/a.png) /files/a.pngx"
		)

		result, count = rewrite.sub(text)

		self.assertEqual(count, 3)
		self.assertEqual(
			result,
			'<img src="/files/k.png"> /files/a.png.bak /files/a.png-2 /other/files/a.png '
			f"x/files/a.png See /files/k.png. ({site}/files/k.png) /files/a.pngx",
		)

	def test_encoded_spellings(self):
		rewrite = build_url_rewrite([UrlChange("/files/a b&c.png", "/files/k l.png")])

		self.assertEqual(rewrite.sub("/files/a%20b&c.png")[0], "/files/k%20l.png")
		self.assertEqual(rewrite.sub("/files/a%20b%26c.png")[0], "/files/k%20l.png")
		# In text, the new URL's space is percent-encoded however the old one was written.
		self.assertEqual(rewrite.sub("/files/a b&amp;c.png")[0], "/files/k%20l.png")
		self.assertEqual(rewrite.sub("/files/a b&c.png")[0], "/files/k%20l.png")
		# An Attach field takes the URL as stored.
		self.assertEqual(rewrite.replacements["/files/a b&c.png"], "/files/k l.png")

	def test_the_new_url_cannot_break_out_of_html_or_markdown(self):
		"""A file name may hold quotes and angle brackets (Frappe only replaces
		`/ \\ % ? #`), and text fields are written without Frappe's sanitising."""
		new = '/files/x" onerror="alert(1)" <b>`.png'
		rewrite = build_url_rewrite([UrlChange("/files/m.png", new)])

		self.assertEqual(
			rewrite.sub('<img src="/files/m.png"> <img src=/files/m.png> [m](/files/m.png)')[0],
			'<img src="/files/x%22%20onerror=%22alert(1)%22%20%3Cb%3E%60.png">'
			" <img src=/files/x%22%20onerror=%22alert(1)%22%20%3Cb%3E%60.png>"
			" [m](/files/x%22%20onerror=%22alert(1)%22%20%3Cb%3E%60.png)",
		)
		self.assertEqual(rewrite.replacements["/files/m.png"], new)

	def test_cloud_storage_key_spellings(self):
		rewrite = build_url_rewrite(
			[UrlChange("/api/method/retrieve?key=f/File/A/a.png", "/api/method/retrieve?key=f/k.png")]
		)

		self.assertEqual(
			rewrite.sub("/api/method/retrieve?key=f%2FFile%2FA%2Fa.png")[0],
			"/api/method/retrieve?key=f%2Fk.png",
		)
		self.assertEqual(
			rewrite.sub("/api/method/retrieve?key=f/File/A/a.png&x=1")[0],
			"/api/method/retrieve?key=f/k.png&x=1",
		)
		self.assertEqual(rewrite.sub("/api/method/retrieve?key=f/File/A/a.png2")[1], 0)

	def test_private_fid(self):
		dropped = build_url_rewrite([UrlChange("/private/files/a.png", "/private/files/k.png", old_fid="M1")])
		kept = build_url_rewrite(
			[UrlChange("/private/files/a.png", "/private/files/k.png", old_fid="M1", new_fid="M1")]
		)

		self.assertEqual(dropped.sub("/private/files/a.png?fid=M1")[0], "/private/files/k.png")
		self.assertEqual(kept.sub("/private/files/a.png?fid=M1")[0], "/private/files/k.png?fid=M1")
		# Another File with the same URL is a copy, which takes the kept file's URL too.
		self.assertEqual(dropped.sub("/private/files/a.png?fid=M12")[0], "/private/files/k.png?fid=M12")

	def test_private_fid_followed_by_another_parameter(self):
		dropped = build_url_rewrite([UrlChange("/private/files/a.png", "/private/files/k.png", old_fid="M1")])
		kept = build_url_rewrite(
			[UrlChange("/private/files/a.png", "/private/files/k.png", old_fid="M1", new_fid="M1")]
		)

		# The fid of a deleted File is dropped, and the next parameter starts the query.
		self.assertEqual(
			dropped.sub('<a href="/private/files/a.png?fid=M1&download=1">')[0],
			'<a href="/private/files/k.png?download=1">',
		)
		self.assertEqual(
			dropped.sub('<a href="/private/files/a.png?fid=M1&amp;download=1">')[0],
			'<a href="/private/files/k.png?download=1">',
		)
		self.assertEqual(
			dropped.sub("/private/files/a.png?fid=M1 and more")[0], "/private/files/k.png and more"
		)
		self.assertEqual(
			kept.sub("/private/files/a.png?fid=M1&amp;download=1")[0],
			"/private/files/k.png?fid=M1&amp;download=1",
		)
		self.assertEqual(
			dropped.sub("/private/files/a.png?fid=M12&download=1")[0],
			"/private/files/k.png?fid=M12&download=1",
		)

	def test_doctypes_without_a_table_or_column_are_skipped(self):
		answers = [["_DS Test Gone", "ToDo", "Website Settings"], [], []]
		get_all = frappe.get_all

		def doctypes_then_real(*args: Any, **kwargs: Any) -> Any:
			return answers.pop(0) if answers else get_all(*args, **kwargs)

		with (
			patch.object(frappe, "get_all", side_effect=doctypes_then_real),
			patch.object(frappe.db, "has_column", return_value=False),
		):
			fields = get_url_fields()

		# A Single keeps its values in tabSingles, so it has no column to check.
		self.assertEqual({f.doctype for f in fields}, {"Website Settings"})

	def test_nothing_to_replace(self):
		rewrite = build_url_rewrite([UrlChange("/files/a.png", "/files/a.png")])

		self.assertEqual(rewrite.replacements, {})
		self.assertEqual(rewrite.sub("/files/a.png"), ("/files/a.png", 0))
		self.assertEqual(fields_with_matches(get_url_fields(), rewrite), [])


class TestMergeFilesGuards(DataStewardIntegrationTestCase):
	def test_disabled_capability_raises_permission_error(self):
		kept, merged = make_file(), make_file()
		set_capability("file_merge", 0)

		with self.assertRaises(frappe.PermissionError):
			merge_files(kept.name, [merged.name])

		self.assertTrue(frappe.db.exists("File", merged.name))

	def test_user_without_system_manager_raises_permission_error(self):
		user = make_user("ds_test_file_merge_item_manager@example.com", "Item Manager")
		kept, merged = make_file(), make_file()

		with (
			self.capability_enabled("file_merge"),
			set_user(user.name),
			self.assertRaises(frappe.PermissionError),
		):
			merge_files(kept.name, [merged.name])

	def test_kept_file_needs_write_permission(self):
		"""Frappe lets a user change a File they uploaded, or one attached to a
		document they can change; a System Manager is no exception."""
		user = make_user("ds_test_file_merge_sysman@example.com", "System Manager")
		kept = make_file()
		with set_user(user.name):
			merged = make_file()

		with (
			self.capability_enabled("file_merge"),
			set_user(user.name),
			self.assertRaises(frappe.PermissionError),
		):
			merge_files(kept.name, [merged.name])

		self.assertTrue(frappe.db.exists("File", merged.name))

	def test_merged_file_needs_delete_permission(self):
		user = make_user("ds_test_file_merge_sysman@example.com", "System Manager")
		others = make_file()
		with set_user(user.name):
			kept, own = make_file(), make_file()

		with self.capability_enabled("file_merge"), set_user(user.name):
			results = merge_files(kept.name, json.dumps([others.name, own.name]))

		self.assertFalse(results[0]["merged"])
		self.assertIn("permission", results[0]["message"].lower())
		self.assertTrue(frappe.db.exists("File", others.name))
		self.assertTrue(results[1]["merged"])
		self.assertFalse(frappe.db.exists("File", own.name))

	def test_refused_files_come_back_as_failed_lines(self):
		kept = make_file()
		private = make_file(is_private=1)
		remote = frappe.get_doc(
			{"doctype": "File", "file_url": "https://example.com/_ds_test.png", "file_name": "_ds_test.png"}
		).insert(ignore_permissions=True)

		messages_before = len(frappe.local.message_log)

		with self.capability_enabled("file_merge"):
			results = merge_files(
				kept.name, [kept.name, "Home", "_DS Test no such file", private.name, remote.name]
			)

		self.assertEqual([r["merged"] for r in results], [False] * 5)
		messages = [r["message"] for r in results]
		self.assertIn("cannot be merged into itself", messages[0])
		self.assertIn("is a folder", messages[1])
		self.assertIn("does not exist", messages[2])
		self.assertIn("not both private or both public", messages[3])
		self.assertIn("stored at an external address", messages[4])
		self.assertTrue(frappe.db.exists("File", private.name))
		self.assertTrue(frappe.db.exists("File", remote.name))
		# Refusals are lines in the log, not message boxes as well.
		self.assertEqual(len(frappe.local.message_log), messages_before)

	def test_kept_file_must_be_a_file_with_content(self):
		merged = make_file()
		missing = make_file()
		os.remove(missing.get_full_path())

		with self.capability_enabled("file_merge"):
			with self.assertRaises(frappe.DoesNotExistError):
				merge_files("_DS Test no such file", [merged.name])
			with self.assertRaisesRegex(frappe.ValidationError, "not a file"):
				merge_files("Home", [merged.name])
			with self.assertRaisesRegex(frappe.ValidationError, "is missing"):
				merge_files(missing.name, [merged.name])

	def test_file_names_must_be_a_short_list(self):
		with self.assertRaisesRegex(frappe.ValidationError, "list of File names"):
			parse_file_names('{"a": 1}')
		with self.assertRaisesRegex(frappe.ValidationError, "at least one"):
			parse_file_names(["", ""])
		with self.assertRaisesRegex(frappe.ValidationError, "At most"):
			parse_file_names([f"f{i}" for i in range(MAX_FILES + 1)])
		self.assertEqual(parse_file_names('["a", "b", "a"]'), ["a", "b"])


class TestMergeFiles(DataStewardIntegrationTestCase):
	def test_attach_image_and_text_editor_are_rewritten(self):
		kept, merged = make_file(file_name="_ds_kept.png"), make_file(file_name="_ds_merged.png")
		site = get_url().rstrip("/")
		old, new = merged.file_url, kept.file_url
		item = _item(
			"_DS Test File Merge Item",
			image=old,
			description=(
				f'<p><img src="{old}"> <a href="{site}{old}">x</a> <a href="{old}.bak">decoy</a> {old}-2</p>'
			),
		)
		decoy = _todo()
		frappe.db.set_value("ToDo", decoy.name, "description", f"{old}.bak")

		with self.capability_enabled("file_merge"):
			results = merge_files(kept.name, [merged.name])

		# one per field and row: the Item's image and its description
		self.assertEqual(results[0]["references"], 2)
		row = frappe.db.get_value("Item", item.name, ["image", "description"], as_dict=True)
		self.assertEqual(row.image, new)
		self.assertEqual(
			row.description,
			f'<p><img src="{new}"> <a href="{site}{new}">x</a> <a href="{old}.bak">decoy</a> {old}-2</p>',
		)
		self.assertEqual(_description(decoy.name), f"{old}.bak")
		self.assertFalse(frappe.db.exists("File", merged.name))

	def test_child_table_and_single_are_rewritten(self):
		kept, merged = make_file(), make_file()
		slideshow = frappe.get_doc(
			{
				"doctype": "Website Slideshow",
				"slideshow_name": "_DS Test File Merge Slides",
				"slideshow_items": [{"image": merged.file_url}],
				"header": f'<img src="{merged.file_url}">',
			}
		).insert(ignore_permissions=True)
		frappe.db.set_single_value("Website Settings", "banner_image", merged.file_url)
		frappe.db.set_single_value("Website Settings", "banner_html", f'<img src="{merged.file_url}">')
		frappe.db.set_single_value("Website Settings", "app_logo", f"{merged.file_url}.bak")
		frappe.db.set_single_value("Website Settings", "head_html", f"{merged.file_url}-2")

		with self.capability_enabled("file_merge"):
			results = merge_files(kept.name, [merged.name])

		self.assertEqual(results[0]["references"], 4)
		slideshow.reload()
		self.assertEqual(slideshow.get("slideshow_items")[0].image, kept.file_url)
		self.assertEqual(slideshow.get("header"), f'<img src="{_in_text(kept.file_url)}">')
		self.assertEqual(frappe.db.get_single_value("Website Settings", "banner_image"), kept.file_url)
		self.assertEqual(
			frappe.db.get_single_value("Website Settings", "banner_html"),
			f'<img src="{_in_text(kept.file_url)}">',
		)
		self.assertEqual(frappe.db.get_single_value("Website Settings", "app_logo"), f"{merged.file_url}.bak")
		self.assertEqual(frappe.db.get_single_value("Website Settings", "head_html"), f"{merged.file_url}-2")

	def test_attached_file_stays_on_its_document(self):
		kept = make_file()
		todo = _todo()
		merged = _attach(to=todo)

		with self.capability_enabled("file_merge"):
			results = merge_files(kept.name, [merged.name])

		self.assertTrue(results[0]["merged"])
		self.assertIn(f"Kept as the attachment of ToDo {todo.name}", results[0]["message"])
		row = frappe.db.get_value(
			"File", merged.name, ["file_url", "content_hash", "attached_to_name"], as_dict=True
		)
		self.assertEqual((row.file_url, row.content_hash), (kept.file_url, kept.content_hash))
		self.assertEqual(row.attached_to_name, todo.name)
		self.assertIn(kept.file_url, [a.file_url for a in get_attachments("ToDo", todo.name)])

	def test_attached_file_is_deleted_when_the_document_has_the_kept_file(self):
		todo = _todo()
		kept, merged = _attach(to=todo), _attach(to=todo)

		with self.capability_enabled("file_merge"):
			results = merge_files(kept.name, [merged.name])

		self.assertEqual(results[0]["message"], "Deleted.")
		self.assertFalse(frappe.db.exists("File", merged.name))
		self.assertEqual([a.name for a in get_attachments("ToDo", todo.name)], [kept.name])

	def test_private_file_links_keep_working(self):
		kept = make_file(is_private=1)
		todo = _todo()
		attached = _attach(is_private=1, to=todo)
		unattached = make_file(is_private=1)
		note = _todo()
		frappe.db.set_value(
			"ToDo",
			note.name,
			"description",
			f'<a href="{attached.file_url}?fid={attached.name}">a</a> '
			f'<a href="{unattached.file_url}?fid={unattached.name}">b</a>',
		)

		with self.capability_enabled("file_merge"):
			merge_files(kept.name, [attached.name, unattached.name])

		self.assertEqual(
			_description(note.name),
			f'<a href="{_in_text(kept.file_url)}?fid={attached.name}">a</a> <a href="{_in_text(kept.file_url)}">b</a>',
		)

	def test_shared_content_never_deletes_the_kept_files_content(self):
		"""Frappe gives a second upload of the same content the first one's URL."""
		content = frappe.generate_hash(length=32).encode()
		kept, merged = make_file(content), make_file(content)
		self.assertEqual(kept.file_url, merged.file_url)

		with self.capability_enabled("file_merge"):
			results = merge_files(kept.name, [merged.name])
		_commit()

		self.assertTrue(results[0]["merged"])
		self.assertFalse(frappe.db.exists("File", merged.name))
		self.assertTrue(os.path.exists(kept.get_full_path()))

	def test_copies_of_shared_content_are_left_alone(self):
		"""When the merged file already uses the kept file's content, the
		attachment copies of that content are the kept file's own: nothing
		about them changes, and the log does not say they were repointed."""
		content = frappe.generate_hash(length=32).encode()
		kept, merged = make_file(content), make_file(content, file_name="_DS Test other name.txt")
		copy = merged.create_attachment_copy("ToDo", _todo().name, ignore_permissions=True)
		before = frappe.db.get_value("File", copy.name, ["file_name", "file_url"], as_dict=True)

		with self.capability_enabled("file_merge"):
			results = merge_files(kept.name, [merged.name])
		_commit()

		self.assertTrue(results[0]["merged"])
		self.assertNotIn("other File record(s)", results[0]["message"])
		self.assertEqual(
			frappe.db.get_value("File", copy.name, ["file_name", "file_url"], as_dict=True), before
		)
		self.assertTrue(os.path.exists(kept.get_full_path()))

	def test_unshared_content_is_deleted_after_the_commit(self):
		kept, merged = make_file(), make_file()
		path = merged.get_full_path()

		with self.capability_enabled("file_merge"):
			merge_files(kept.name, [merged.name])
		self.assertTrue(os.path.exists(path))
		_commit()

		self.assertFalse(os.path.exists(path))
		self.assertTrue(os.path.exists(kept.get_full_path()))

	def test_thumbnail_is_deleted_unless_used(self):
		kept, merged, other = make_file(), make_file(), make_file()
		thumbnail = f"/files/_ds_test_thumb_{frappe.generate_hash(length=8)}.png"
		path = frappe.get_site_path("public", thumbnail.lstrip("/"))
		with open(path, "wb") as f:
			f.write(b"thumb")
		self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
		frappe.db.set_value("File", merged.name, "thumbnail_url", thumbnail)
		frappe.db.set_value("File", other.name, "thumbnail_url", thumbnail)

		with self.capability_enabled("file_merge"):
			merge_files(kept.name, [merged.name])
		_commit()
		self.assertTrue(os.path.exists(path))

		with self.capability_enabled("file_merge"):
			merge_files(kept.name, [other.name])
		_commit()
		self.assertFalse(os.path.exists(path))

	def test_copies_of_the_merged_content_follow_it(self):
		kept, merged = make_file(), make_file()
		todo = _todo()
		copy = merged.create_attachment_copy("ToDo", todo.name, ignore_permissions=True)
		path = merged.get_full_path()

		with self.capability_enabled("file_merge"):
			results = merge_files(kept.name, [merged.name])
		_commit()

		self.assertIn("1 other File record(s)", results[0]["message"])
		self.assertEqual(frappe.db.get_value("File", copy.name, "file_url"), kept.file_url)
		self.assertFalse(os.path.exists(path))

	def test_a_url_in_another_case_is_another_file(self):
		"""MariaDB compares `/files/A.png` and `/files/a.png` as equal; on the
		disk, and to Frappe, they are two files."""
		suffix = frappe.generate_hash(length=8)
		kept = make_file(file_name=f"_ds_case_kept_{suffix}.png")
		merged = make_file(file_name=f"_ds_case_{suffix}.png")
		other = make_file(file_name=f"_DS_CASE_{suffix}.png")
		self.assertEqual(other.file_url.lower(), merged.file_url.lower())
		self.assertNotEqual(other.file_url, merged.file_url)
		item = _item("_DS Test File Merge Case", image=other.file_url)

		with self.capability_enabled("file_merge"):
			results = merge_files(kept.name, [merged.name])
		_commit()

		self.assertTrue(results[0]["merged"], results[0]["message"])
		self.assertEqual(results[0]["message"], "Deleted.")
		self.assertEqual(frappe.db.get_value("Item", item.name, "image"), other.file_url)
		self.assertEqual(frappe.db.get_value("File", other.name, "file_url"), other.file_url)
		self.assertTrue(os.path.exists(other.get_full_path()))
		# On a case-insensitive disk the two would be one file, so the merged
		# content is only removed when no URL in any case uses it.
		self.assertTrue(os.path.exists(merged.get_full_path()))

	def test_an_attachment_in_another_case_is_not_the_kept_file(self):
		suffix = frappe.generate_hash(length=8)
		kept = make_file(file_name=f"_ds_case_{suffix}.png")
		todo = _todo()
		_attach(file_name=f"_DS_CASE_{suffix}.png", to=todo)
		merged = _attach(to=todo)

		with self.capability_enabled("file_merge"):
			results = merge_files(kept.name, [merged.name])

		self.assertIn(f"Kept as the attachment of ToDo {todo.name}", results[0]["message"])
		self.assertEqual(frappe.db.get_value("File", merged.name, "file_url"), kept.file_url)

	def test_a_kept_url_with_quotes_stays_inside_the_attribute(self):
		kept = make_file(file_name='_ds_x" onerror="alert(1)".png')
		self.assertIn('"', kept.file_url)
		merged = make_file()
		item = _item(
			"_DS Test File Merge Quote", image=merged.file_url, description=f'<img src="{merged.file_url}">'
		)

		with self.capability_enabled("file_merge"):
			merge_files(kept.name, [merged.name])

		row = frappe.db.get_value("Item", item.name, ["image", "description"], as_dict=True)
		self.assertEqual(row.image, kept.file_url)
		encoded = kept.file_url.replace('"', "%22").replace(" ", "%20")
		self.assertEqual(row.description, f'<img src="{encoded}">')

	def test_derived_caches_are_cleared_after_the_commit(self):
		kept, merged = make_file(), make_file()
		cache = frappe.cache
		assert cache is not None
		_item("_DS Test File Merge Cache", image=merged.file_url)
		cache.hset("bootinfo", "_ds_test@example.com", {"app_logo_url": merged.file_url})

		with self.capability_enabled("file_merge"):
			merge_files(kept.name, [merged.name])
		self.assertIsNotNone(cache.hget("bootinfo", "_ds_test@example.com"))
		with patch("frappe.website.utils.clear_cache") as clear_website_cache:
			_commit()

		self.assertIsNone(cache.hget("bootinfo", "_ds_test@example.com"))
		clear_website_cache.assert_called_with()

	def test_nothing_merged_clears_no_cache(self):
		kept = make_file()

		with (
			self.capability_enabled("file_merge"),
			patch.object(file_merge, "clear_derived_caches") as clear_derived_caches,
		):
			results = merge_files(kept.name, ["_ds_no_such_file"])
			_commit()

		self.assertFalse(results[0]["merged"])
		clear_derived_caches.assert_not_called()

	def test_a_website_theme_is_named_for_a_rebuild(self):
		kept, merged = make_file(), make_file()
		theme = frappe.get_doc(
			{
				"doctype": "Website Theme",
				"name": "_DS Test File Merge Theme",
				"theme": "_DS Test File Merge Theme",
				"custom": 1,
				"custom_scss": f"body {{ background: url({merged.file_url}); }}",
			}
		)
		theme.db_insert()

		with self.capability_enabled("file_merge"):
			results = merge_files(kept.name, [merged.name])

		self.assertIn("Save Website Theme _DS Test File Merge Theme to rebuild", results[0]["message"])
		self.assertEqual(
			frappe.db.get_value("Website Theme", theme.name, "custom_scss"),
			f"body {{ background: url({_in_text(kept.file_url)}); }}",
		)

	def test_comments_move_and_the_kept_file_records_the_merge(self):
		kept, merged = make_file(), make_file(file_name="_ds_merged_audit.txt")
		merged.add_comment("Comment", "_DS Test note on the merged file")
		_item("_DS Test File Merge Audit", image=merged.file_url)

		with self.capability_enabled("file_merge"):
			merge_files(kept.name, [merged.name])

		comments = frappe.get_all(
			"Comment",
			filters={"reference_doctype": "File", "reference_name": kept.name},
			fields=["comment_type", "content"],
		)
		self.assertIn("_DS Test note on the merged file", [c.content for c in comments])
		audit = next(c.content for c in comments if c.comment_type == "Edit")
		self.assertIn(f"Merged _ds_merged_audit.txt ({merged.name}, {merged.file_url})", audit)
		self.assertIn("References changed to this file: 1.", audit)

	def test_one_failure_does_not_undo_the_others(self):
		kept, first, second = make_file(), make_file(), make_file()
		item_a = _item("_DS Test File Merge A", image=first.file_url)
		item_b = _item("_DS Test File Merge B", image=second.file_url)
		delete_merged_row = file_merge.delete_merged_row

		def fail_first(merged: File) -> None:
			if merged.name == first.name:
				raise frappe.ValidationError("_DS Test boom")
			delete_merged_row(merged)

		with (
			self.capability_enabled("file_merge"),
			patch.object(file_merge, "delete_merged_row", side_effect=fail_first),
		):
			results = merge_files(kept.name, [first.name, second.name])

		self.assertEqual([r["merged"] for r in results], [False, True])
		self.assertEqual(results[0]["message"], "_DS Test boom")
		self.assertEqual(frappe.db.get_value("Item", item_a.name, "image"), first.file_url)
		self.assertTrue(frappe.db.exists("File", first.name))
		self.assertEqual(frappe.db.get_value("Item", item_b.name, "image"), kept.file_url)
		self.assertFalse(frappe.db.exists("File", second.name))

	def test_link_fields_in_a_single_are_counted(self):
		"""No standard Single links to a File, so this one is given its link
		fields; Frappe's own `update_link_field_values` changes them."""
		kept, merged = make_file(), make_file()
		frappe.db.set_single_value("Website Settings", "banner_image", merged.name)
		link_fields = [
			{"parent": "Website Settings", "fieldname": "banner_image", "issingle": 1},
			{"parent": "Website Settings", "fieldname": "app_logo", "issingle": 1},
			{"parent": "File", "fieldname": "folder", "issingle": 0},
		]
		outcome = _Outcome()

		with (
			patch.object(file_merge, "get_link_fields", return_value=link_fields),
			patch.object(file_merge, "update_link_field_values") as update,
		):
			rewrite_links(merged.name, kept.name, outcome)

		self.assertEqual(outcome.references, 1)
		update.assert_called_once_with(link_fields, merged.name, kept.name, "File")

	def test_a_failed_cleanup_is_logged(self):
		kept, merged = make_file(), make_file()

		with self.capability_enabled("file_merge"):
			merge_files(kept.name, [merged.name])
		with (
			patch("data_steward.data_steward.hooks.file_storage._remove_local", side_effect=OSError("boom")),
			patch.object(frappe, "log_error") as log_error,
		):
			_commit()

		log_error.assert_called_once()
