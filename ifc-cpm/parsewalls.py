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

target_wall_id = '162023'

for storey in model.by_type("IfcBuildingStorey"):
    elements = ifcopenshell.util.element.get_decomposition(storey)
    ifc_wall = find(elements, lambda x: target_wall_id in x.Name)
    if not ifc_wall:
        continue

    ifc_doors = [x for x in ifcopenshell.util.element.get_decomposition(ifc_wall) if x.is_a("IfcDoor")]
    for ifc_door in ifc_doors:
        opening_container = ifcopenshell.util.element.get_container(ifc_door, "IfcOpeningElement")
        if opening_container:
            continue
        print(ifc_door)
        shape = ifcopenshell.geom.create_shape(settings, ifc_door)
        matrix = ifcopenshell.util.placement.get_local_placement(ifc_door.ObjectPlacement)
        vertices = ifcopenshell.util.shape.get_vertices(shape.geometry)

        print(matrix)
        print(vertices)
