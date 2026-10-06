"""Structured logging for Real Aquatics SAP integration. Every SAP attempt (success or failure) is recorded in Real Aquatics SAP Log."""
import json
import frappe

MAX_PAYLOAD_LEN = 5000


def _truncate(s, max_len=MAX_PAYLOAD_LEN):
	if s is None:
		return None
	if isinstance(s, (dict, list)):
		s = json.dumps(s, default=str, indent=0)
	else:
		s = str(s)
	return s[:max_len] + ("..." if len(s) > max_len else "")


def log_real_aquatics_sap(
	reference_doctype,
	reference_name,
	operation,
	status,
	request_payload=None,
	response_payload=None,
	error_message=None,
):
	"""Create a Real Aquatics SAP Log entry. Call after each SAP attempt (success or failure).

	Intentionally does NOT call frappe.db.commit() — the caller controls the transaction
	boundary. Committing inside a logging helper breaks atomicity and causes partial
	state to be persisted when the outer operation fails.
	"""
	try:
		log = frappe.get_doc(
			doctype="Real Aquatics SAP Log",
			reference_doctype=reference_doctype or "",
			reference_name=reference_name or "",
			operation=operation or "",
			status=status,
			error_message=(error_message or "")[:5000] if error_message else None,
			request_payload=_truncate(request_payload),
			response_payload=_truncate(response_payload),
		)
		log.insert(ignore_permissions=True)
	except Exception as e:
		# Avoid very long Error Log titles; keep the title short and put details in the message.
		frappe.log_error("Real Aquatics SAP Log", f"Real Aquatics SAP Log insert failed: {e}")
