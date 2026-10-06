import frappe
from frappe.utils import get_request_session
from .exceptions import InvalidRequest, AuthenticationError, GatewayError



# class RazorpaySettings(Document):
# 	def validate(self):
# 		validate_razorpay_credentials(razorpay_settings=frappe._dict({
# 			"api_key": self.api_key,
# 			"api_secret": self.get_password(fieldname="api_secret")
# 		}))


def validate_razorpay_credentials():

	try:
		get_request(url="https://api.razorpay.com/v1/payments", auth=frappe._dict({
			"api_key": "rzp_test_9cgztgtG8oGziw",
			"api_secret": "WMfNIl52MJOUwEWWKcM5iML1"
		}))
	except AuthenticationError as e:
		frappe.throw(_(e.message))

def get_request(url, auth=None):
	res = None
	if not auth:
		return

	try:
		s = get_request_session()
		res = s.get(url, data={}, auth=(auth.api_key, auth.api_secret))
		res.raise_for_status()
		return res.json()
	except Exception as exc:
		raise_exception(res, exc)