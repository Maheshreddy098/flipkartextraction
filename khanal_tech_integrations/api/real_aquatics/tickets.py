import io
import json
import mimetypes
import time
from datetime import datetime

import boto3
import frappe
from frappe import _
from frappe.utils import now_datetime

from khanal_tech_integrations.api.real_aquatics.auth import (
	check_real_aquatics_access,
	get_user_team,
	get_user_real_aquatics_roles,
)


REALAQUATICS_TICKET_BUCKET = "realaquatics-tickets"
REALAQUATICS_TICKET_REGION = "us-west-1"


def _get_real_aquatics_s3_client():
	aws = frappe.get_single("AWS")
	if not aws.wowpets_access_key_id:
		frappe.throw(_("Real Aquatics S3 credentials are not configured in the AWS doctype"), frappe.ValidationError)
	secret = aws.get_password("wowpets_secret_access_key")
	if not secret:
		frappe.throw(_("Real Aquatics S3 secret access key is not configured in the AWS doctype"), frappe.ValidationError)
	region = aws.wowpets_region or REALAQUATICS_TICKET_REGION
	return boto3.client(
		"s3",
		aws_access_key_id=aws.wowpets_access_key_id,
		aws_secret_access_key=secret,
		region_name=region,
	)

SECTION_PREFIX_MAP = {
	"Purchase Order": "PurchaseOrder",
	"Work Order": "WorkOrder",
	"FBA Transfer": "InventoryTransfer",
	"Shiphero Transfer": "InventoryTransfer",
	"Dispatch Order": "DispatchOrders",
	"Dispatch Orders": "DispatchOrders",
}


_check_real_aquatics_access = check_real_aquatics_access


def _ensure_ticket_permissions(ticket):
	if not frappe.has_permission("Real Aquatics Ticket", doc=ticket, ptype="read"):
		frappe.throw(_("Not permitted to access this ticket"), frappe.PermissionError)


def _get_section_prefix(section: str) -> str:
	section = (section or "").strip()
	if not section:
		return "Other"
	return SECTION_PREFIX_MAP.get(section, section.replace(" ", ""))


def _get_s3_client():
	return _get_real_aquatics_s3_client()


def _upload_ticket_file_to_s3(section: str, ticket_name: str, filename: str, content: bytes) -> str:
	prefix = _get_section_prefix(section)
	safe_ticket = (ticket_name or "").replace(" ", "_").replace("/", "_")
	base_filename = (filename or "attachment").replace(" ", "_").replace("/", "_")
	name, ext = (base_filename.rsplit(".", 1) + [""])[:2]
	if ext:
		ext = "." + ext
	timestamp = str(int(time.time()))
	sanitized_filename = f"{name}_{timestamp}{ext}"
	key = f"{prefix}/{safe_ticket}/{sanitized_filename}"

	max_size = 50 * 1024 * 1024
	if len(content or b"") > max_size:
		frappe.throw(
			_("File {0} is too large (max 50MB)").format(filename or sanitized_filename),
			frappe.ValidationError,
		)

	s3 = _get_s3_client()
	content_type = mimetypes.guess_type(sanitized_filename)[0] or "application/octet-stream"
	s3.upload_fileobj(
		Fileobj=io.BytesIO(content),
		Bucket=REALAQUATICS_TICKET_BUCKET,
		Key=key,
		ExtraArgs={
			"ContentType": content_type,
			"Metadata": {
				"original_filename": filename or sanitized_filename,
				"uploaded_at": datetime.utcnow().isoformat(),
				"source": "RealAquatics_Tickets",
			},
		},
	)

	if REALAQUATICS_TICKET_REGION == "us-east-1":
		return f"https://{REALAQUATICS_TICKET_BUCKET}.s3.amazonaws.com/{key}"
	return f"https://{REALAQUATICS_TICKET_BUCKET}.s3.{REALAQUATICS_TICKET_REGION}.amazonaws.com/{key}"


@frappe.whitelist()
def get_list(status=None, section=None, page=1, page_size=20):
	_check_real_aquatics_access()

	filters = {}
	if status:
		filters["status"] = status
	if section:
		filters["section"] = section

	team = get_user_team()
	if team == "warehouse":
		filters["raised_team"] = "warehouse"

	tickets = frappe.get_list(
		"Real Aquatics Ticket",
		filters=filters,
		fields=[
			"name",
			"title",
			"ticket_type",
			"section",
			"reference_doctype",
			"reference_name",
			"status",
			"priority",
			"raised_by",
			"raised_team",
			"assigned_to",
			"modified",
		],
		order_by="modified desc",
		start=(int(page) - 1) * int(page_size),
		page_length=int(page_size),
	)
	total = frappe.db.count("Real Aquatics Ticket", filters=filters)
	return {"data": tickets, "total": total}


@frappe.whitelist()
def get_detail(name):
	_check_real_aquatics_access()
	doc = frappe.get_doc("Real Aquatics Ticket", name)
	_ensure_ticket_permissions(doc)
	return doc.as_dict()


def _normalize_ticket_payload(data):
	if isinstance(data, str):
		data = json.loads(data)
	if not isinstance(data, dict):
		frappe.throw(_("Invalid payload"), frappe.ValidationError)
	return data


@frappe.whitelist()
def create(data):
	_check_real_aquatics_access()
	data = _normalize_ticket_payload(data)

	title = (data.get("title") or "").strip()
	if not title:
		frappe.throw(_("Title is required"))

	section = (data.get("section") or "").strip()
	if not section:
		frappe.throw(_("Section is required"))

	if not (data.get("description") or "").strip():
		frappe.throw(_("Description is required"))

	doc = frappe.new_doc("Real Aquatics Ticket")
	doc.title = title
	doc.ticket_type = data.get("ticket_type") or "Operational"
	doc.section = section
	doc.reference_doctype = data.get("reference_doctype")
	doc.reference_name = data.get("reference_name")
	doc.status = "Open"
	doc.priority = data.get("priority") or "Medium"
	doc.description = data.get("description")
	doc.raised_by = frappe.session.user
	doc.raised_team = get_user_team() or "khanalfoods"
	doc.assigned_to = data.get("assigned_to")
	doc.insert()
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def update(name, data):
	_check_real_aquatics_access()
	data = _normalize_ticket_payload(data)

	doc = frappe.get_doc("Real Aquatics Ticket", name)
	_ensure_ticket_permissions(doc)

	old_status = doc.status
	team = get_user_team()

	if "title" in data:
		doc.title = (data.get("title") or "").strip() or doc.title
	if "ticket_type" in data and data.get("ticket_type"):
		doc.ticket_type = data.get("ticket_type")
	if "section" in data and data.get("section"):
		doc.section = data.get("section")
	if "reference_doctype" in data:
		doc.reference_doctype = data.get("reference_doctype")
	if "reference_name" in data:
		doc.reference_name = data.get("reference_name")
	if "status" in data and data.get("status"):
		if team == "warehouse":
			frappe.throw(_("Only KhanalFoods team can change ticket status"), frappe.PermissionError)
		doc.status = data.get("status")
	if "priority" in data and data.get("priority"):
		if team == "warehouse":
			frappe.throw(_("Only KhanalFoods team can change ticket priority"), frappe.PermissionError)
		doc.priority = data.get("priority")
	if "description" in data and data.get("description") is not None:
		doc.description = data.get("description")
	if "resolution_notes" in data and data.get("resolution_notes") is not None:
		if team == "warehouse":
			frappe.throw(_("Only KhanalFoods team can set resolution notes"), frappe.PermissionError)
		doc.resolution_notes = data.get("resolution_notes")
	if "assigned_to" in data:
		if team == "warehouse":
			frappe.throw(_("Only KhanalFoods team can assign tickets"), frappe.PermissionError)
		doc.assigned_to = data.get("assigned_to")

	doc.save()
	frappe.db.commit()

	# If status changed, notify the other side via email.
	if "status" in data and data.get("status") and data.get("status") != old_status:
		try:
			from frappe.utils.user import get_users_with_role

			current_user = frappe.session.user
			recipients = set()

			if doc.assigned_to and doc.assigned_to != current_user:
				recipients.add(doc.assigned_to)

			if doc.raised_by and doc.raised_by != current_user:
				recipients.add(doc.raised_by)

			if not recipients:
				if (doc.raised_team or "").lower() == "warehouse":
					for u in get_users_with_role("RealAquatics KhanalFoods User"):
						if u != current_user:
							recipients.add(u)
				else:
					for u in get_users_with_role("RealAquatics Warehouse User"):
						if u != current_user:
							recipients.add(u)

			if recipients:
				frappe.sendmail(
					recipients=list(recipients),
					subject=_("Real Aquatics Ticket {0} status changed to {1}").format(doc.name, doc.status),
					message=_(
						"<p><b>{title}</b></p>"
						"<p>Status changed from <b>{old}</b> to <b>{new}</b>.</p>"
					).format(
						title=frappe.utils.escape_html(doc.title or ""),
						old=frappe.utils.escape_html(old_status or ""),
						new=frappe.utils.escape_html(doc.status or ""),
					),
					reference_doctype="Real Aquatics Ticket",
					reference_name=doc.name,
				)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Real Aquatics Ticket status change notification failed")

	return doc.as_dict()


@frappe.whitelist()
def add_attachment(ticket_name: str, file_name: str, filedata: str):
	"""Add an attachment to a Real Aquatics Ticket.

	Expects filedata as base64 string from the frontend.
	"""
	_check_real_aquatics_access()

	if not ticket_name:
		frappe.throw(_("Ticket name is required"), frappe.ValidationError)

	ticket = frappe.get_doc("Real Aquatics Ticket", ticket_name)
	_ensure_ticket_permissions(ticket)
	if not frappe.has_permission("Real Aquatics Ticket", doc=ticket, ptype="write"):
		frappe.throw(_("Not permitted to add attachments to this ticket"), frappe.PermissionError)

	if not file_name:
		frappe.throw(_("File name is required"), frappe.ValidationError)
	if not filedata:
		frappe.throw(_("File data is required"), frappe.ValidationError)

	import base64

	try:
		content = base64.b64decode(filedata)
	except Exception:
		frappe.throw(_("Invalid file data"), frappe.ValidationError)

	url = _upload_ticket_file_to_s3(ticket.section, ticket.name, file_name, content)

	row = ticket.append("attachments", {})
	row.file_name = file_name
	row.file_url = url
	row.uploaded_by = frappe.session.user
	row.uploaded_on = now_datetime()
	ticket.save()
	frappe.db.commit()

	return {
		"file_name": row.file_name,
		"file_url": row.file_url,
		"uploaded_by": row.uploaded_by,
		"uploaded_on": row.uploaded_on,
	}


@frappe.whitelist()
def list_attachments(ticket_name: str):
	if not ticket_name:
		frappe.throw(_("Ticket name is required"), frappe.ValidationError)
	ticket = frappe.get_doc("Real Aquatics Ticket", ticket_name)
	_ensure_ticket_permissions(ticket)
	return [
		{
			"file_name": a.file_name,
			"file_url": a.file_url,
			"uploaded_by": a.uploaded_by,
			"uploaded_on": a.uploaded_on,
		}
		for a in (ticket.attachments or [])
	]


@frappe.whitelist()
def add_comment(ticket_name: str, content: str):
	if not ticket_name:
		frappe.throw(_("Ticket name is required"), frappe.ValidationError)
	if not (content or "").strip():
		frappe.throw(_("Comment cannot be empty"), frappe.ValidationError)

	_check_real_aquatics_access()
	ticket = frappe.get_doc("Real Aquatics Ticket", ticket_name)
	_ensure_ticket_permissions(ticket)

	row = ticket.append("comments", {})
	row.content = content.strip()
	ticket.save()
	frappe.db.commit()

	# Notify the other side via email so they know a new reply arrived.
	# Basic rule:
	# - If warehouse raised the ticket, email KhanalFoods side (assigned_to or default role inbox).
	# - If KhanalFoods raised the ticket, email the warehouse side (raised_by / assigned_to).
	try:
		from frappe.utils.user import get_users_with_role

		current_user = frappe.session.user
		recipients = set()

		if ticket.assigned_to and ticket.assigned_to != current_user:
			recipients.add(ticket.assigned_to)

		if ticket.raised_by and ticket.raised_by != current_user:
			recipients.add(ticket.raised_by)

		# Fallback by team if no explicit users could be determined
		if not recipients:
			if (ticket.raised_team or "").lower() == "warehouse":
				for u in get_users_with_role("RealAquatics KhanalFoods User"):
					if u != current_user:
						recipients.add(u)
			else:
				for u in get_users_with_role("RealAquatics Warehouse User"):
					if u != current_user:
						recipients.add(u)

		if recipients:
			frappe.sendmail(
				recipients=list(recipients),
				subject=_("New reply on Real Aquatics Ticket {0}").format(ticket.name),
				message=_(
					"<p><b>{title}</b></p>"
					"<p>{body}</p>"
					"<p>Status: {status} | Priority: {priority}</p>"
				).format(
					title=frappe.utils.escape_html(ticket.title or ""),
					body=frappe.utils.escape_html(row.content or ""),
					status=frappe.utils.escape_html(ticket.status or ""),
					priority=frappe.utils.escape_html(ticket.priority or ""),
				),
				reference_doctype="Real Aquatics Ticket",
				reference_name=ticket.name,
			)
	except Exception:
		# Notification failure should not block comment creation
		frappe.log_error(frappe.get_traceback(), "Real Aquatics Ticket add_comment notification failed")

	return {
		"content": row.content,
		"owner": row.owner,
		"creation": row.creation,
	}


@frappe.whitelist()
def list_comments(ticket_name: str):
	if not ticket_name:
		frappe.throw(_("Ticket name is required"), frappe.ValidationError)
	_check_real_aquatics_access()
	ticket = frappe.get_doc("Real Aquatics Ticket", ticket_name)
	_ensure_ticket_permissions(ticket)
	return [
		{
			"content": c.content,
			"owner": c.owner,
			"creation": c.creation,
		}
		for c in (ticket.comments or [])
	]

