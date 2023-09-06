import copy
from typing import List
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from lib.ifctypes import Wall, Gate, BuildingElement
from lib.representation_helpers import WallVertices

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, False)

model = ifcopenshell.open("ifc/Project3_2.ifc")
unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)

for storey in model.by_type("IfcBuildingStorey"):
    elements = ifcopenshell.util.element.get_decomposition(storey)
    walls = [x for x in elements if x.is_a("IfcWall")]

    print(storey.Name)
    for wall in walls:
        representations = wall.Representation.Representations

        transformation_matrix = ifcopenshell.util.placement.get_local_placement(
            wall.ObjectPlacement
        )

        print(wall.Name)
        print(transformation_matrix)
        print((representations[0].Items[0].Points))
        vertices = WallVertices.infer(representations)
        print("vertices", vertices)
        v1, v2 = vertices
        mat1 = np.array([[v1[0]], [v1[1]], [0], [1]])
        mat2 = np.array([[v2[0]], [v2[1]], [0], [1]])
        print(np.dot(transformation_matrix, mat2))

        # print(transformation_matrix)

        # v1, v2 = representations[0].Items[0].Points[0].Coordinates

        # mat = np.array([[v1[0]], [v1[1]], [v1[2]], [0]])
        # mat2 = np.array([[v2[0]], [v2[1]], [v2[2]], [0]])
        # print(mat)
        # print(np.dot(transformation_matrix, mat))
        # print(np.dot(transformation_matrix, mat2))
        print()
