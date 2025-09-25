"""
Hub'Eau Data Integration Pipeline
Point d'entrée principal - Structure Dagster standard
"""

# Import des définitions centrales
from .definitions import defs

# Export pour Dagster
__all__ = ["defs"]