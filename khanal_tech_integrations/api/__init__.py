
from bs4 import BeautifulSoup
import frappe
from frappe.translate import get_all_translations
from frappe.utils import cstr

# Import plant modules to ensure they are loaded and discoverable by Frappe
# This ensures all whitelisted endpoints are registered
try:
    from . import plants
except ImportError:
    # Silently fail if plants module is not available
    pass

# Import unicommerce dashboard module to ensure it's loaded and discoverable by Frappe
try:
    from . import unicommerce_dashboard
    # Force registration by accessing a function
    _ = unicommerce_dashboard.test_endpoint
except ImportError as e:
    # Log the error for debugging.
    # frappe.log_error(title, message) — title first, and it's capped at 140
    # chars (the Error Log doctype's Title column). Passing the long f-string
    # positionally as the first arg put it in title instead of message, so a
    # long exception message crashed with CharacterLengthExceededError instead
    # of being logged — turning this deliberate "log and continue" guard into
    # a hard failure. Keyword args make the correct order unambiguous.
    frappe.log_error(title="API Import Error", message=f"Failed to import unicommerce_dashboard: {str(e)}")
except Exception as e:
    # Log any other errors — same argument-order fix as above.
    frappe.log_error(title="API Import Error", message=f"Error loading unicommerce_dashboard: {str(e)}")

@frappe.whitelist(allow_guest=True)
def get_translations():
	if frappe.session.user != "Guest":
		language = frappe.db.get_value("User", frappe.session.user, "language")
	else:
		language = frappe.db.get_single_value("System Settings", "language")

	return get_all_translations(language)


@frappe.whitelist()
def get_user_signature():
	user = frappe.session.user
	user_email_signature = (
		frappe.db.get_value(
			"User",
			user,
			"email_signature",
		)
		if user
		else None
	)

	signature = user_email_signature or frappe.db.get_value(
		"Email Account",
		{"default_outgoing": 1, "add_signature": 1},
		"signature",
	)

	if not signature:
		return

	soup = BeautifulSoup(signature, "html.parser")
	html_signature = soup.find("div", {"class": "ql-editor read-mode"})
	_signature = None
	if html_signature:
		_signature = html_signature.renderContents()
	content = ""
	if (cstr(_signature) or signature):
		content = f'<br><p class="signature">{signature}</p>'
	return content




