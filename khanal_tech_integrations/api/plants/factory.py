"""
Factory pattern for getting plant-specific APIs
"""

import frappe


class PlantAPIFactory:
    """Factory to get plant-specific API instances"""
    
    @staticmethod
    def get_grn_api(plant_id):
        """
        Get GRN API for specific plant
        
        Args:
            plant_id (str): Plant identifier
            
        Returns:
            BaseGRNAPI: Plant-specific GRN API instance
        """
        if plant_id == 'malur':
            from .malur.grn import MalurGRNAPI
            return MalurGRNAPI()
        elif plant_id == 'krishnagiri':
            from .krishnagiri.grn import KrishnagiriGRNAPI
            return KrishnagiriGRNAPI()
        elif plant_id == 'champavath':
            from .champavath.grn import ChampavathGRNAPI
            return ChampavathGRNAPI()
        elif plant_id == 'nandi_hills':
            from .nandi_hills.grn import NandiHillsGRNAPI
            return NandiHillsGRNAPI()
        else:
            frappe.throw(f"Unknown plant: {plant_id}")
    
    @staticmethod
    def get_production_api(plant_id):
        """
        Get Production API for specific plant
        
        Args:
            plant_id (str): Plant identifier
            
        Returns:
            BaseProductionAPI: Plant-specific Production API instance
        """
        if plant_id == 'malur':
            # Future: from .malur.production import MalurProductionAPI
            # return MalurProductionAPI()
            frappe.throw(f"Production API not implemented for plant: {plant_id}")
        else:
            frappe.throw(f"Unknown plant: {plant_id}")

