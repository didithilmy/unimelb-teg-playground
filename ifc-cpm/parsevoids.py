import copy
from typing import List
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from lib.ifctypes import Wall, Gate, BuildingElement
from lib.representation_helpers import Extrusion2DVertices

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

model = ifcopenshell.open("ifc/Project3.ifc")
unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)


for storey in model.by_type("IfcBuildingStorey"):
    print(storey.Name)
    elements = ifcopenshell.util.element.get_decomposition(storey)
    slabs = [x for x in elements if x.is_a("IfcSlab")]
    floor_slabs = [x for x in slabs if x.PredefinedType == "FLOOR"]
    if len(floor_slabs) > 0:
        floor = floor_slabs[0]
        floor_openings = floor.HasOpenings
        for floor_opening in floor_openings:
            opening_element = floor_opening.RelatedOpeningElement
            print(opening_element.Name)
            representations = opening_element.Representation.Representations
            print((representations[0].Items[0].SweptArea.OuterCurve.Points.CoordList))
            vertices = Extrusion2DVertices.infer(representations)
            print(vertices)

            print((opening_element.ObjectPlacement.RelativePlacement))
            # print((opening_element.ObjectPlacement.RelativePlacement.Location))
            opening_location_relative_to_slab = (
                opening_element.ObjectPlacement.RelativePlacement.Location.Coordinates
            )

            axis = opening_element.ObjectPlacement.RelativePlacement.Axis

            x, y, z = opening_location_relative_to_slab
            print(x, y, z)

            # matrix = ifcopenshell.util.placement.get_local_placement(
            #     opening_element.ObjectPlacement
            # )

            # coord_mat = np.array([[0], [0], [0], [1]])

            # floor_placement = floor.ObjectPlacement
            # floor_matrix = ifcopenshell.util.placement.get_local_placement(
            #     floor_placement
            # )
            # print("Floor placement", floor_matrix)
            # transformed = np.dot(matrix, coord_mat)
            # print(transformed)

#     for wall in walls:
#         print(wall.Name)
#         for opening in wall.HasOpenings:
#             opening_element = opening.RelatedOpeningElement
#             representations = [t
#                 x
#                 for x in opening_element.Representation.Representations
#                 if x.RepresentationIdentifier == "Box"
#             ]
#             box_representation = representations[0]
#             opening_length = box_representation.Items[0].XDim
#             # print(opening_length)

#             opening_location_relative_to_wall = (
#                 opening_element.ObjectPlacement.RelativePlacement.Location.Coordinates
#             )
# print((opening_location_relative_to_wall))
# print(dir(opening_element))
# matrix = ifcopenshell.util.placement.get_local_placement(opening_element.ObjectPlacement)
# print(matrix)
# print(opening_element.Name, (opening_element.Representation.Representations[1].Items))
# Opening length can be retrieved from IfcBoundingBox here

# get_opening_vertices(opening)
# print("Opening", opening.Name, opening)
