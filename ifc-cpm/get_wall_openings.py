import copy
from typing import List
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from cpm_writer import CrowdSimulationEnvironment, Level
from lib.ifctypes import Wall, Gate, BuildingElement

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

model = ifcopenshell.open("house.ifc")
unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)

for ifc_wall in model.by_type("IfcWall"):
    print()
    print(ifc_wall.Name)
    openings = ifc_wall.HasOpenings
    for opening in openings:
        opening_element = opening.RelatedOpeningElement
        # matrix = ifcopenshell.util.placement.get_local_placement(opening_element.ObjectPlacement)
        # print(matrix)
        print(dir(opening_element))
        # print(opening_element.ObjectPlacement)
