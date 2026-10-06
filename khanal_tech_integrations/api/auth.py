"""
Authentication API for Plant-Specific Kiosk System
Handles user authentication, plant access control, and session management
"""

import frappe
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta
from frappe import _
from frappe.utils import now, get_datetime, get_url
import json

@frappe.whitelist(allow_guest=True)
def verify_plant_access(user, plant_id):
    """
    Verify if user has access to the specified plant
    
    Args:
        user (str): User email
        plant_id (str): Plant ID to check access for
    
    Returns:
        dict: Access verification result
    """
    try:
        # Get user document
        user_doc = frappe.get_doc("User", user)
        if not user_doc:
            return {"has_access": False, "message": "User not found"}
        
        # Check if user is active
        if user_doc.enabled == 0:
            return {"has_access": False, "message": "User account is disabled"}
        
        # Get plant document by plant_id field
        plants = frappe.get_all(
            "Plant",
            filters={"plant_id": plant_id},
            fields=["name", "plant_id", "plant_name", "location", "status"]
        )
        if not plants:
            return {"has_access": False, "message": "Plant not found"}
        
        plant = plants[0]
        plant_doc = frappe.get_doc("Plant", plant.name)
        
        # Check if plant is active
        if plant_doc.status != "Active":
            return {"has_access": False, "message": "Plant is not active"}
        
        # Check user plant access
        user_plant_access = frappe.get_all(
            "User Plant Access",
            filters={
                "user": user,
                "plant": plant.name,
                "enabled": 1
            },
            fields=["name", "role", "permissions"]
        )
        
        # Check if user's email is in the plant's allowed emails (whitelist)
        has_whitelist_access = False
        if hasattr(plant_doc, 'allowed_emails') and plant_doc.allowed_emails:
            allowed_emails_list = [email.strip().lower() for email in plant_doc.allowed_emails.split(',')]
            if user.lower() in allowed_emails_list:
                has_whitelist_access = True
        
        if not user_plant_access and not has_whitelist_access:
            return {"has_access": False, "message": "No access to this plant"}
        
        # Get plant information
        plant_info = {
            "plant_id": plant_id,
            "plant_name": plant_doc.plant_name,
            "location": plant_doc.location,
            "type": "Primary Production Facility",
            "status": plant_doc.status
        }
        
        # Prepare user access information
        user_access_info = None
        if user_plant_access:
            user_access_info = user_plant_access[0]
        elif has_whitelist_access:
            # User has whitelist access but no explicit User Plant Access record
            user_access_info = {
                "name": None,
                "role": None,
                "permissions": None,
                "access_via": "whitelist"
            }
        
        return {
            "has_access": True,
            "plant_name": plant_doc.plant_name,
            "plant_info": plant_info,
            "user_access": user_access_info
        }
        
    except Exception as e:
        frappe.log_error(f"Error verifying plant access: {str(e)}")
        return {"has_access": False, "message": "Error verifying access"}

@frappe.whitelist(allow_guest=True)
def get_user_permissions(user, plant_id):
    """
    Get user permissions for the specified plant
    
    Args:
        user (str): User email
        plant_id (str): Plant ID
    
    Returns:
        list: List of permissions
    """
    try:
        # Get plant document to check whitelist
        plants = frappe.get_all(
            "Plant",
            filters={"plant_id": plant_id},
            fields=["name"]
        )
        
        if not plants:
            return []
        
        plant_doc = frappe.get_doc("Plant", plants[0].name)
        
        # Check if user has whitelist access
        has_whitelist_access = False
        if hasattr(plant_doc, 'allowed_emails') and plant_doc.allowed_emails:
            allowed_emails_list = [email.strip().lower() for email in plant_doc.allowed_emails.split(',')]
            if user.lower() in allowed_emails_list:
                has_whitelist_access = True
        
        # Get user plant access
        user_plant_access = frappe.get_all(
            "User Plant Access",
            filters={
                "user": user,
                "plant": plants[0].name,
                "enabled": 1
            },
            fields=["permissions", "role"]
        )
        
        if not user_plant_access and not has_whitelist_access:
            return []
        
        # Parse custom permissions from User Plant Access record
        permissions = []
        if user_plant_access and user_plant_access[0].permissions:
            try:
                permissions = json.loads(user_plant_access[0].permissions)
            except:
                permissions = []
        
        # Get role-based permissions from Frappe Role doctype
        if user_plant_access and user_plant_access[0].role:
            role_name = user_plant_access[0].role
            # You can extend this to fetch role-specific permissions from a custom field in Role doctype
            # For now, just add the role name as a permission identifier
            permissions.append(f"role:{role_name}")
        
        # If user has whitelist access but no User Plant Access record, give basic view permissions
        if has_whitelist_access and not user_plant_access:
            permissions.append("whitelist_access")
        
        return list(set(permissions))  # Remove duplicates
        
    except Exception as e:
        frappe.log_error(f"Error getting user permissions: {str(e)}")
        return []

@frappe.whitelist(allow_guest=True)
def generate_plant_token(user, plant_id, permissions):
    """
    Generate JWT token with plant-specific information
    
    Args:
        user (str): User email
        plant_id (str): Plant ID
        permissions (list): User permissions
    
    Returns:
        dict: Token and user data
    """
    try:
        # Get user document
        user_doc = frappe.get_doc("User", user)
        if not user_doc:
            frappe.throw("User not found")
        
        # Get plant document by plant_id field
        plant_docs = frappe.get_all(
            "Plant",
            filters={"plant_id": plant_id},
            fields=["name", "plant_id", "plant_name", "location", "status"]
        )
        
        if not plant_docs:
            frappe.throw("Plant not found")
        
        plant_doc = frappe.get_doc("Plant", plant_docs[0].name)
        
        # Generate JWT payload
        now = datetime.utcnow()
        payload = {
            "user_id": user,
            "plant_id": plant_id,
            "plant_name": plant_doc.plant_name,
            "user_roles": [role.role for role in user_doc.roles],
            "permissions": permissions,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=8)).timestamp())  # 8 hour expiry
        }
        
        # For now, use a simple token to avoid JWT complexity
        # This will allow the frontend to work while we debug JWT issues
        simple_token = f"plant_token_{user}_{plant_id}_{frappe.generate_hash()[:16]}"
        
        # Prepare user data
        user_data = {
            "email": user_doc.email,
            "name": user_doc.full_name or user_doc.first_name,
            "role": user_doc.roles[0].role if user_doc.roles else "User",
            "roles": [role.role for role in user_doc.roles],
            "last_login": user_doc.last_login,
            "user_image": user_doc.user_image
        }
        
        return {
            "token": simple_token,
            "user_data": user_data,
            "expires_at": (datetime.utcnow() + timedelta(hours=8)).isoformat()
        }
        
    except Exception as e:
        frappe.log_error(f"Error generating plant token: {str(e)}")
        frappe.throw("Error generating authentication token")

@frappe.whitelist()
def verify_session(user, plant_id):
    """
    Verify if the current session is valid
    
    Args:
        user (str): User email
        plant_id (str): Plant ID
    
    Returns:
        dict: Session verification result
    """
    try:
        # Get current user
        current_user = frappe.get_user()
        if current_user.name != user:
            return {"valid": False, "message": "User mismatch"}
        
        # Verify plant access
        access_result = verify_plant_access(user, plant_id)
        if not access_result.get("has_access"):
            return {"valid": False, "message": "No plant access"}
        
        return {"valid": True, "message": "Session is valid"}
        
    except Exception as e:
        frappe.log_error(f"Error verifying session: {str(e)}")
        return {"valid": False, "message": "Error verifying session"}

@frappe.whitelist()
def refresh_token(token, user, plant_id):
    """
    Refresh JWT token
    
    Args:
        token (str): Current JWT token
        user (str): User email
        plant_id (str): Plant ID
    
    Returns:
        dict: New token
    """
    try:
        # Verify current token
        jwt_secret = frappe.get_conf().get("jwt_secret")
        if not jwt_secret:
            frappe.throw("JWT secret not configured")
        
        try:
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            frappe.throw("Token has expired")
        except jwt.InvalidTokenError:
            frappe.throw("Invalid token")
        
        # Verify user and plant match
        if payload.get("user_id") != user or payload.get("plant_id") != plant_id:
            frappe.throw("Token user/plant mismatch")
        
        # Generate new token with same permissions
        new_payload = {
            "user_id": user,
            "plant_id": plant_id,
            "plant_name": payload.get("plant_name"),
            "user_roles": payload.get("user_roles", []),
            "permissions": payload.get("permissions", []),
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=8)
        }
        
        new_token = jwt.encode(new_payload, jwt_secret, algorithm="HS256")
        
        return {
            "token": new_token,
            "expires_at": new_payload["exp"].isoformat()
        }
        
    except Exception as e:
        frappe.log_error(f"Error refreshing token: {str(e)}")
        frappe.throw("Error refreshing token")

@frappe.whitelist(allow_guest=True)
def request_password_reset(email, plant_id=None):
    """
    Request password reset for user
    
    Args:
        email (str): User email
        plant_id (str): Plant ID
    
    Returns:
        dict: Reset request result
    """
    try:
        # Ensure user exists
        try:
            frappe.get_doc("User", email)
        except Exception:
            return {"success": False, "message": "User not found"}

        # If plant_id provided, optionally validate access but don't block core reset
        if plant_id:
            access_result = verify_plant_access(email, plant_id)
            if not access_result.get("has_access"):
                return {"success": False, "message": "No access to this plant"}

        # Prefer Frappe core reset_password (sends email) for reliability
        try:
            reset_password = frappe.get_attr('frappe.core.doctype.user.user.reset_password')
            result = reset_password(user=email)
            return {"success": True, "message": _("Password reset link sent to your email")}
        except Exception:
            # Fallback: generate a temporary token and return a link (dev only)
            reset_token = secrets.token_urlsafe(32)
            frappe.cache().set_value(
                f"password_reset_{reset_token}",
                {
                    "user": email,
                    "plant_id": plant_id,
                    "timestamp": now()
                },
                expires_in_sec=3600
            )
            reset_url = f"{get_url()}/kiosk/reset-password?token={reset_token}&plant={plant_id or ''}"
            return {"success": True, "message": _("Password reset link generated"), "reset_url": reset_url}
        
    except Exception as e:
        frappe.log_error(f"Error requesting password reset: {str(e)}")
        return {"success": False, "message": "Error processing reset request"}

@frappe.whitelist(allow_guest=True)
def reset_password_with_token(token, new_password):
    """
    Reset password using a one-time token stored in cache (dev-friendly flow).
    """
    try:
        if not token or not new_password:
            frappe.throw("Missing token or new password")

        data = frappe.cache().get_value(f"password_reset_{token}")
        if not data or not data.get("user"):
            frappe.throw("Invalid or expired reset link")

        user_email = data["user"]
        user_doc = frappe.get_doc("User", user_email)
        user_doc.new_password = new_password
        user_doc.save(ignore_permissions=True)

        # Invalidate token
        frappe.cache().delete_value(f"password_reset_{token}")

        return {"success": True, "message": _("Password has been reset. You can now log in.")}

    except Exception as e:
        frappe.log_error(f"Error resetting password with token: {str(e)}")
        frappe.throw("Could not reset password")

@frappe.whitelist()
def change_password(current_password, new_password, plant_id):
    """
    Change user password
    
    Args:
        current_password (str): Current password
        new_password (str): New password
        plant_id (str): Plant ID
    
    Returns:
        dict: Password change result
    """
    try:
        # Get current user
        user = frappe.get_user()
        
        # Verify current password
        if not frappe.utils.password.check_password(user.name, current_password):
            frappe.throw("Current password is incorrect")
        
        # Update password using User doc API (sets hashed password correctly)
        user_doc = frappe.get_doc("User", user.name)
        user_doc.new_password = new_password
        user_doc.save(ignore_permissions=True)
        
        return {"success": True, "message": "Password changed successfully"}
        
    except Exception as e:
        frappe.log_error(f"Error changing password: {str(e)}")
        frappe.throw("Error changing password")

@frappe.whitelist(allow_guest=True)
def get_plants():
    """
    Get all available plants
    
    Returns:
        list: List of plants
    """
    try:
        plants = frappe.get_all(
            "Plant",
            fields=["name", "plant_id", "plant_name", "location", "status"],
            filters={"status": "Active"},
            order_by="plant_name"
        )
        
        # Format plant data
        formatted_plants = []
        for plant in plants:
            formatted_plants.append({
                "id": plant.plant_id or plant.name,  # Use plant_id if available, fallback to name
                "name": plant.plant_name,
                "location": plant.location,
                "type": "Primary Production Facility",  # Default type
                "icon": "🏭",  # Default icon
                "description": f"Production facility in {plant.location}",
                "status": plant.status
            })
        
        return formatted_plants
        
    except Exception as e:
        frappe.log_error(f"Error fetching plants: {str(e)}")
        frappe.throw("Error fetching plants")

@frappe.whitelist(allow_guest=True)
def get_plant_details(plant_id):
    """
    Get detailed information about a specific plant
    
    Args:
        plant_id (str): Plant ID
    
    Returns:
        dict: Plant details
    """
    try:
        plant_doc = frappe.get_doc("Plant", plant_id)
        if not plant_doc:
            frappe.throw("Plant not found")
        
        return {
            "id": plant_doc.plant_id or plant_doc.name,  # Use plant_id if available, fallback to name
            "name": plant_doc.plant_name,
            "location": plant_doc.location,
            "type": plant_doc.plant_type,
            "icon": plant_doc.icon or "🏭",
            "description": plant_doc.description,
            "status": plant_doc.status,
            "capacity": getattr(plant_doc, 'capacity', None),
            "operating_hours": getattr(plant_doc, 'operating_hours', None),
            "manager": getattr(plant_doc, 'manager', None),
            "contact": getattr(plant_doc, 'contact', None),
            "email": getattr(plant_doc, 'email', None)
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching plant details: {str(e)}")
        frappe.throw("Error fetching plant details")

@frappe.whitelist(allow_guest=True)
def get_user_plants(user):
    """
    Get plants accessible by a specific user
    
    Args:
        user (str): User email
    
    Returns:
        list: List of accessible plants
    """
    try:
        # Get user plant access records
        user_plants = frappe.get_all(
            "User Plant Access",
            fields=["plant"],
            filters={"user": user, "enabled": 1},
            order_by="plant"
        )
        
        plants_from_access = set([up.plant for up in user_plants])
        
        # Also check for plants with user in whitelist
        all_plants = frappe.get_all(
            "Plant",
            fields=["name", "plant_name", "location", "plant_type", "icon", "description", "status", "allowed_emails"],
            filters={"status": "Active"}
        )
        
        # Get plant details
        plants = []
        for plant in all_plants:
            # Check if user has explicit access or whitelist access
            has_access = plant.name in plants_from_access
            
            if not has_access and plant.allowed_emails:
                allowed_emails_list = [email.strip().lower() for email in plant.allowed_emails.split(',')]
                if user.lower() in allowed_emails_list:
                    has_access = True
            
            if has_access and plant.status == "Active":
                plants.append({
                    "id": plant.name,
                    "name": plant.plant_name,
                    "location": plant.location,
                    "type": plant.plant_type if hasattr(plant, 'plant_type') else "Production Facility",
                    "icon": plant.icon if hasattr(plant, 'icon') and plant.icon else "🏭",
                    "description": plant.description if hasattr(plant, 'description') else f"Plant in {plant.location}"
                })
        
        return plants
        
    except Exception as e:
        frappe.log_error(f"Error fetching user plants: {str(e)}")
        frappe.throw("Error fetching user plants")

@frappe.whitelist(allow_guest=True)
def get_plant_stats(plant_id):
    """
    Get plant statistics and metrics
    
    Args:
        plant_id (str): Plant ID
    
    Returns:
        dict: Plant statistics
    """
    try:
        # This would typically fetch real statistics from various DocTypes
        # For now, returning mock data structure
        return {
            "production": "15,000L",
            "quality": 98.5,
            "efficiency": 94,
            "orders": 12,
            "departments": 4,
            "employees": 45,
            "last_updated": now()
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching plant stats: {str(e)}")
        frappe.throw("Error fetching plant statistics")

@frappe.whitelist(allow_guest=True)
def get_plant_departments(plant_id):
    """
    Get departments for a specific plant
    
    Args:
        plant_id (str): Plant ID

    Returns:
        list: List of departments
    """
    try:
        # This would typically fetch from a Department DocType
        # For now, returning mock data
        departments = [
            {
                "id": "milk-processing",
                "name": "Milk Processing",
                "description": "Primary milk processing operations",
                "status": "Active",
                "efficiency": 95,
                "icon": "🥛"
            },
            {
                "id": "yogurt-production",
                "name": "Yogurt Production",
                "description": "Yogurt manufacturing and packaging",
                "status": "Active",
                "efficiency": 88,
                "icon": "🍶"
            },
            {
                "id": "cheese-making",
                "name": "Cheese Making",
                "description": "Artisan cheese production",
                "status": "Active",
                "efficiency": 92,
                "icon": "🧀"
            },
            {
                "id": "packaging",
                "name": "Packaging",
                "description": "Final packaging and quality control",
                "status": "Active",
                "efficiency": 97,
                "icon": "📦"
            }
        ]
        
        return departments
        
    except Exception as e:
        frappe.log_error(f"Error fetching plant departments: {str(e)}")
        frappe.throw("Error fetching plant departments")

