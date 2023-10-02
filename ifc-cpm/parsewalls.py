import copy
from typing import List
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.shape
import ifcopenshell.util.unit
from compas.geometry import oriented_bounding_box_xy_numpy
from lib.ifctypes import Wall, Gate, BuildingElement
from lib.representation_helpers import WallVertices, XYBoundingBox
from lib.utils import transform_vertex_3d, eucledian_distance, find, find_unbounded_lines_intersection, truncate, get_oriented_xy_bounding_box, get_edge_from_bounding_box, transform_vertex

from skspatial.objects import Line

settings = ifcopenshell.geom.settings()

model = ifcopenshell.open("ifc/rac_advanced_sample_project.ifc")
unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)

for storey in model.by_type("IfcBuildingStorey"):
    elements = ifcopenshell.util.element.get_decomposition(storey)
    ifc_wall = find(elements, lambda x: '182328' in x.Name)
    if not ifc_wall:
        continue

    wall_vertices = WallVertices.from_product(ifc_wall)
    print("Wall edge", wall_vertices)

    gates_vertices = []
    openings = ifc_wall.HasOpenings
    for opening in openings:
        opening_element = opening.RelatedOpeningElement
        print(opening_element.PredefinedType)
        if opening_element.PredefinedType.upper() != 'RECESS':
            shape = ifcopenshell.geom.create_shape(settings, opening_element)
            vertices = ifcopenshell.util.shape.get_vertices(shape.geometry)

            bbox = get_oriented_xy_bounding_box(vertices)
            v1, v2 = get_edge_from_bounding_box(bbox)

            matrix = ifcopenshell.util.placement.get_local_placement(opening_element.ObjectPlacement)
            v1 = transform_vertex(matrix, v1)
            v2 = transform_vertex(matrix, v2)

            wall_line = Line.from_points(wall_vertices[0], wall_vertices[1])
            v1_projected = wall_line.project_point(v1)
            v2_projected = wall_line.project_point(v2)

            print("Opening edge", (v1_projected, v2_projected))
