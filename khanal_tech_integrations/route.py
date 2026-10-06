routes=[
	# Legacy intranet routes
	{'from_route': '/intranet/deliveryhistory/<docentry>','to_route':'intranet/deliveryhistory'},
	
	# Main kiosk SPA routes (explicit to avoid catching assets)
	{'from_route': '/kiosk','to_route':'kiosk'},
	{'from_route': '/kiosk/login','to_route':'kiosk'},
	{'from_route': '/kiosk/reset-password','to_route':'kiosk'},
	{'from_route': '/kiosk/unauthorized','to_route':'kiosk'},
	{'from_route': '/kiosk/plant-selection','to_route':'kiosk'},
	{'from_route': '/kiosk/login/<plant_id>','to_route':'kiosk'},
	
	# Plant-specific routes
	{'from_route': '/kiosk/plant/<plant_id>','to_route':'kiosk'},
	{'from_route': '/kiosk/plant/<plant_id>/dashboard','to_route':'kiosk'},
	{'from_route': '/kiosk/plant/<plant_id>/grn','to_route':'kiosk'},
	{'from_route': '/kiosk/plant/<plant_id>/production-order','to_route':'kiosk'},
	{'from_route': '/kiosk/plant/<plant_id>/quality','to_route':'kiosk'},
	{'from_route': '/kiosk/plant/<plant_id>/inventory-transfer','to_route':'kiosk'},
	{'from_route': '/kiosk/plant/<plant_id>/disassembly','to_route':'kiosk'},
	{'from_route': '/kiosk/plant/<plant_id>/<feature>','to_route':'kiosk'},
	
	# API routes for kiosk
	{'from_route': '/api/kiosk/<path:path>','to_route':'kiosk_api'},
	
	# Admin routes
	{'from_route': '/kiosk/admin','to_route':'kiosk'},
	{'from_route': '/kiosk/admin/<path:path>','to_route':'kiosk'},
	
	# Batch generator route
	{'from_route': '/kiosk/batch-generator','to_route':'kiosk'},

	# Ghee Reverse Production Order
	{'from_route': '/kiosk/ghee-production-order','to_route':'kiosk'},
	{'from_route': '/kiosk/ghee-production-order/<path:path>','to_route':'kiosk'},

	# WowPets 3PL SPA routes
	{'from_route': '/wowpets','to_route':'wowpets'},
	{'from_route': '/wowpets/login','to_route':'wowpets'},
	{'from_route': '/wowpets/khanalfoods','to_route':'wowpets'},
	{'from_route': '/wowpets/khanalfoods/<path:path>','to_route':'wowpets'},
	{'from_route': '/wowpets/warehouse','to_route':'wowpets'},
	{'from_route': '/wowpets/warehouse/<path:path>','to_route':'wowpets'},

	# Real Aquatics 3PL SPA routes
	{'from_route': '/realaquatics','to_route':'realaquatics'},
	{'from_route': '/realaquatics/login','to_route':'realaquatics'},
	{'from_route': '/realaquatics/khanalfoods','to_route':'realaquatics'},
	{'from_route': '/realaquatics/khanalfoods/<path:path>','to_route':'realaquatics'},
	{'from_route': '/realaquatics/warehouse','to_route':'realaquatics'},
	{'from_route': '/realaquatics/warehouse/<path:path>','to_route':'realaquatics'},

	# StoreOps SPA routes
	{'from_route': '/storeops','to_route':'storeops'},
	{'from_route': '/storeops/login','to_route':'storeops'},
	{'from_route': '/storeops/dashboard','to_route':'storeops'},
	{'from_route': '/storeops/inventory','to_route':'storeops'},
	{'from_route': '/storeops/inventory/<plant_code>','to_route':'storeops'},
	{'from_route': '/storeops/transfers','to_route':'storeops'},
	{'from_route': '/storeops/transfers/<path:path>','to_route':'storeops'},
	{'from_route': '/storeops/delivery','to_route':'storeops'},
	{'from_route': '/storeops/delivery/<path:path>','to_route':'storeops'},
	{'from_route': '/storeops/procurement','to_route':'storeops'},
	{'from_route': '/storeops/admin','to_route':'storeops'},
	{'from_route': '/storeops/admin/<path:path>','to_route':'storeops'},

	# Amazon US Ops Console SPA routes
	{'from_route': '/amazonus','to_route':'amazonus'},
	{'from_route': '/amazonus/orders','to_route':'amazonus'},
	{'from_route': '/amazonus/actions','to_route':'amazonus'},
	{'from_route': '/amazonus/settlements','to_route':'amazonus'},
	{'from_route': '/amazonus/credit-notes','to_route':'amazonus'},
]
