import base64
import io
import mimetypes
import time

import boto3
import frappe
from frappe import _
from frappe.utils import now_datetime

from khanal_tech_integrations.api.real_aquatics.auth import (
	check_real_aquatics_access,
	get_user_team,
	get_user_real_aquatics_roles,
)

MODULE_FOLDER_MAP = {
	"Real Aquatics Order": "fba-transfers",
	"Real Aquatics Work Order": "work-orders",
	"Real Aquatics Purchase Order": "purchase-orders",
	"Real Aquatics Dispatch Order": "dispatch-orders",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


_check_real_aquatics_access = check_real_aquatics_access


def _check_khanalfoods_access():
	team = get_user_team()
	if team != "khanalfoods":
		frappe.throw(_("Only KhanalFoods team can upload attachments"), frappe.PermissionError)


def _get_aws_config():
	"""Read AWS doctype once and return (s3_client, bucket_name). Centralises credential access."""
	aws = frappe.get_single("AWS")
	if not aws.wowpets_access_key_id:
		frappe.throw(
			_("Real Aquatics S3 credentials are not configured in the AWS doctype"),
			frappe.ValidationError,
		)
	secret = aws.get_password("wowpets_secret_access_key")
	if not secret:
		frappe.throw(
			_("Real Aquatics S3 secret access key is not configured in the AWS doctype"),
			frappe.ValidationError,
		)
	region = aws.wowpets_region or "us-west-1"
	bucket = aws.real_aquatics_khanalfoods_bucket or "realaquatics-khanalfoods"
	client = boto3.client(
		"s3",
		aws_access_key_id=aws.wowpets_access_key_id,
		aws_secret_access_key=secret,
		region_name=region,
	)
	return client, bucket


def _get_s3_client():
	client, _ = _get_aws_config()
	return client


def _get_bucket_name():
	_, bucket = _get_aws_config()
	return bucket


def _get_module_folder(doctype: str) -> str:
	folder = MODULE_FOLDER_MAP.get(doctype)
	if not folder:
		frappe.throw(_("Attachments not supported for doctype: {0}").format(doctype), frappe.ValidationError)
	return folder


@frappe.whitelist()
def upload_attachment(doctype, docname, file_name, filedata):
	"""Upload a file to S3 and record it in Real Aquatics KF Attachment.
	KhanalFoods team only.
	filedata must be base64-encoded string.
	"""
	_check_real_aquatics_access()
	_check_khanalfoods_access()

	if not docname:
		frappe.throw(_("Document must be saved before attaching files"), frappe.ValidationError)

	module_folder = _get_module_folder(doctype)

	try:
		content = base64.b64decode(filedata)
	except Exception:
		frappe.throw(_("Invalid file data — expected base64 encoded content"), frappe.ValidationError)

	if len(content) > MAX_FILE_SIZE:
		frappe.throw(_("File is too large (max 50 MB)"), frappe.ValidationError)

	safe_docname = (docname or "").replace(" ", "_").replace("/", "_")
	base_filename = (file_name or "attachment").replace(" ", "_").replace("/", "_")
	name, ext = (base_filename.rsplit(".", 1) + [""])[:2]
	ext_str = ("." + ext) if ext else ""
	timestamp = str(int(time.time()))
	sanitized_filename = f"{name}_{timestamp}{ext_str}"

	s3_key = f"{module_folder}/{safe_docname}/{sanitized_filename}"
	bucket = _get_bucket_name()
	content_type = mimetypes.guess_type(sanitized_filename)[0] or "application/octet-stream"

	s3 = _get_s3_client()
	s3.upload_fileobj(
		Fileobj=io.BytesIO(content),
		Bucket=bucket,
		Key=s3_key,
		ExtraArgs={
			"ContentType": content_type,
			"Metadata": {
				"original_filename": file_name or sanitized_filename,
				"doctype": doctype,
				"docname": docname,
				"uploaded_by": frappe.session.user,
			},
		},
	)

	doc = frappe.get_doc({
		"doctype": "Real Aquatics KF Attachment",
		"reference_doctype": doctype,
		"reference_name": docname,
		"module_folder": module_folder,
		"file_name": file_name or sanitized_filename,
		"s3_key": s3_key,
		"uploaded_by": frappe.session.user,
		"uploaded_at": now_datetime(),
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	return {
		"name": doc.name,
		"file_name": doc.file_name,
		"uploaded_by": doc.uploaded_by,
		"uploaded_at": str(doc.uploaded_at),
	}


@frappe.whitelist()
def list_attachments(doctype, docname):
	"""List attachments for a document with presigned download URLs.
	Any Real Aquatics user (both teams) can call this.
	"""
	_check_real_aquatics_access()

	records = frappe.get_all(
		"Real Aquatics KF Attachment",
		filters={"reference_doctype": doctype, "reference_name": docname},
		fields=["name", "file_name", "s3_key", "uploaded_by", "uploaded_at"],
		order_by="uploaded_at asc",
	)

	if not records:
		return []

	# Read AWS config once for all records instead of once per record.
	s3, bucket = _get_aws_config()
	result = []

	for row in records:
		try:
			download_url = s3.generate_presigned_url(
				"get_object",
				Params={"Bucket": bucket, "Key": row["s3_key"]},
				ExpiresIn=3600,
			)
		except Exception as e:
			frappe.log_error(
				f"Failed to generate presigned URL for key {row['s3_key']}: {e}",
				"Real Aquatics KF Attachment presigned URL error",
			)
			download_url = None

		result.append({
			"name": row["name"],
			"file_name": row["file_name"],
			"uploaded_by": row["uploaded_by"],
			"uploaded_at": str(row["uploaded_at"]),
			"download_url": download_url,
		})

	return result


def _delete_all_doc_attachments(doctype, docname):
	"""Delete all S3 files and Frappe records for a document. Internal use — call before deleting the parent doc."""
	records = frappe.get_all(
		"Real Aquatics KF Attachment",
		filters={"reference_doctype": doctype, "reference_name": docname},
		fields=["name", "s3_key"],
	)
	if not records:
		return
	try:
		s3, bucket = _get_aws_config()
		for row in records:
			try:
				s3.delete_object(Bucket=bucket, Key=row["s3_key"])
			except Exception as e:
				frappe.log_error(f"S3 delete failed for key {row['s3_key']}: {e}", "Real Aquatics KF Attachment Delete")
	except Exception as e:
		frappe.log_error(f"S3 connection failed during doc attachment cleanup for {doctype}/{docname}: {e}", "Real Aquatics KF Attachment Delete")
	for row in records:
		try:
			frappe.delete_doc("Real Aquatics KF Attachment", row["name"], ignore_permissions=True)
		except Exception as e:
			frappe.log_error(f"Could not delete KF Attachment record {row['name']}: {e}", "Real Aquatics KF Attachment Delete")


@frappe.whitelist()
def delete_attachment(name):
	"""Delete an attachment from S3 and Frappe.
	Only the uploader or a KhanalFoods Manager can delete.
	"""
	_check_real_aquatics_access()

	doc = frappe.get_doc("Real Aquatics KF Attachment", name)

	team = get_user_team()
	roles = get_user_real_aquatics_roles()
	is_manager = "RealAquatics KhanalFoods Manager" in roles
	is_owner = doc.uploaded_by == frappe.session.user

	if team != "khanalfoods" or (not is_manager and not is_owner):
		frappe.throw(_("You do not have permission to delete this attachment"), frappe.PermissionError)

	# Capture S3 key before deleting the Frappe record.
	s3_key = doc.s3_key

	# Delete the Frappe record first — this is transactional and can be rolled back.
	# S3 deletion is non-transactional, so it must happen after the DB commit.
	frappe.delete_doc("Real Aquatics KF Attachment", name, ignore_permissions=True)
	frappe.db.commit()

	# Now delete from S3. If this fails, the Frappe record is already gone but the
	# S3 object becomes an orphan (no ghost attachment visible to users).
	try:
		s3 = _get_s3_client()
		bucket = _get_bucket_name()
		s3.delete_object(Bucket=bucket, Key=s3_key)
	except Exception as e:
		frappe.log_error(f"S3 delete failed for key {s3_key}: {e}", "Real Aquatics KF Attachment Delete")
		# Do not re-raise — Frappe record is gone; S3 orphan can be cleaned up separately.

	return {"success": True}
