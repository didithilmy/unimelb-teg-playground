import copy
from typing import List
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from lib.ifctypes import Wall, Gate, BuildingElement

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

model = ifcopenshell.open("house.ifc")
unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)

for stair in model.by_type("IfcRailing"):
    print()
    print(stair)
    print((stair.Representation.Representations[1].Items[0].XDim))

# stairs = model.by_type("IfcStair")


# # Function to find connected building storeys for a given stair
# def find_connected_building_storeys(stair):
#     connected_storeys = []

#     # Look for relationships where the stair is contained
#     for rel in stair.ContainedInStructure:
#         if rel.RelatingStructure.is_a("IfcBuildingStorey"):
#             connected_storeys.append(rel.RelatingStructure)

#     return connected_storeys


# # Print information about stairs and their connected building storeys
# for stair in stairs:
#     connected_storeys = find_connected_building_storeys(stair)

#     print("Stair ID:", stair.id())
#     print("Connected Building Storeys:")
#     for storey in connected_storeys:
#         print("- Storey ID:", storey.id())
#         print("- Storey Name:", storey.Name)
#         # You can access other properties of the storey as well
#         # For example: storey.GlobalId, storey.Elevation, etc.
#         print("-" * 20)
#     print("=" * 30)

# print("Total Stairs:", len(stairs))
