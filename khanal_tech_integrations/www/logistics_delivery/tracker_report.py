from khanal_tech_integrations.utils.logistics_delivery_portal import ensure_logistics_portal_access


def get_context(context):
    ensure_logistics_portal_access()
    context.no_cache = 1
