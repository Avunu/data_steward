# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""Shared test harness for `data_steward`.

Every whitelisted function in this app starts with `assert_capability(...)`
(see `data_steward/data_steward/doctype/data_steward_settings/data_steward_settings.py`),
so every S1 test needs a cheap way to flip one flag on `Data Steward Settings`
(a Single) for the duration of a test and know it will not leak into the
next one. That is what `DataStewardIntegrationTestCase.capability_enabled`
gives you::

    from data_steward.tests import DataStewardIntegrationTestCase


    class TestSomething(DataStewardIntegrationTestCase):
        def test_it(self):
            with self.capability_enabled("item_convert_to_variant"):
                ...

Commits are suppressed the same way our other apps' live-database test
harnesses do it: the app's own endpoints no longer commit, but
`bulk_rename` (behind `bulk_merge`) commits per row.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import frappe
from frappe.tests import IntegrationTestCase

if TYPE_CHECKING:
	from collections.abc import Generator

__all__ = ["DataStewardIntegrationTestCase"]


class DataStewardIntegrationTestCase(IntegrationTestCase):
	"""Base class for every `data_steward` test."""

	_commit_patcher: Any = None

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()

		from unittest.mock import MagicMock, patch

		cls._commit_patcher = patch.object(frappe.db, "commit", MagicMock())
		cls._commit_patcher.start()
		cls.addClassCleanup(cls._commit_patcher.stop)

	@classmethod
	def tearDownClass(cls) -> None:
		frappe.db.rollback()
		if cls._commit_patcher:
			cls._commit_patcher.stop()
			cls._commit_patcher = None
		super().tearDownClass()

	@contextmanager
	def capability_enabled(self, capability: str) -> Generator[None]:
		"""Turn one Data Steward Settings capability on for the block, off after.

		`assert_capability`/`check_capability` read `Data Steward Settings`
		through `frappe.get_cached_doc`, so this goes through `.save()`
		(which clears that cache) rather than raw SQL.
		"""
		settings = frappe.get_doc("Data Steward Settings")
		previous = settings.get(capability)
		settings.set(capability, 1)
		settings.save(ignore_permissions=True)
		try:
			yield
		finally:
			settings.reload()
			settings.set(capability, previous)
			settings.save(ignore_permissions=True)
