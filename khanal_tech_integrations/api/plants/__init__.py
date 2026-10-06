"""
Plant-specific API modules
Organized by plant for better maintainability
All plants: Malur, Krishnagiri, Champavath, Nandi Hills
"""

from .factory import PlantAPIFactory
from . import malur
from . import krishnagiri
from . import champavath
from . import nandi_hills

__all__ = [
    'PlantAPIFactory',
    'malur',
    'krishnagiri',
    'champavath',
    'nandi_hills'
]

