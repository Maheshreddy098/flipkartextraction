# Copyright (c) 2025, Khanal Tech and Contributors
# See license.txt

# import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class UnitTestB2B_Customer_Details(UnitTestCase):
	"""
	Unit tests for B2B_Customer_Details.
	Use this class for testing individual functions and methods.
	"""

	pass


class IntegrationTestB2B_Customer_Details(IntegrationTestCase):
	"""
	Integration tests for B2B_Customer_Details.
	Use this class for testing interactions between multiple components.
	"""

	pass
