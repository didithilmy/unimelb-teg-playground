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
from lib.representation_helpers import WallVertices
from lib.utils import transform_vertex_3d, eucledian_distance

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, False)

model = ifcopenshell.open("ifc/rac_advanced_sample_project.ifc")
unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)


def get_composite_verts(ifc_product):
    if ifc_product.Representation is not None:
        settings = ifcopenshell.geom.settings()
        shape = ifcopenshell.geom.create_shape(settings, ifc_product)
        vertices = ifcopenshell.util.shape.get_vertices(shape.geometry)
        return list(vertices)

    vertices = []
    for decomposition in ifc_product.IsDecomposedBy:
        relobjects = decomposition.RelatedObjects
        for relobj in relobjects:
            rel_vertices = get_composite_verts(relobj)
            placement = relobj.ObjectPlacement
            matrix = ifcopenshell.util.placement.get_local_placement(placement)
            rel_vertices = [transform_vertex_3d(matrix, x) for x in rel_vertices]
            vertices += rel_vertices

    return vertices


def get_edge_from_bbox(bbox):
    v1, v2, v3, v4 = bbox
    e1 = (v1, v2)
    e2 = (v2, v3)

    e1_dist = eucledian_distance(v1, v2)
    e2_dist = eucledian_distance(v2, v3)

    if e1_dist < e2_dist:
        midpoint_vertex = e1
        run_vertex = e2
    else:
        midpoint_vertex = e2
        run_vertex = e1

    midpoint_x = (midpoint_vertex[0][0] + midpoint_vertex[1][0]) / 2
    midpoint_y = (midpoint_vertex[0][1] + midpoint_vertex[1][1]) / 2

    delta_x = run_vertex[1][0] - run_vertex[0][0]
    delta_y = run_vertex[1][1] - run_vertex[0][1]

    x2 = midpoint_x + delta_x
    y2 = midpoint_y + delta_y

    return (midpoint_x, midpoint_y), (x2, y2)


for storey in model.by_type("IfcBuildingStorey"):
    elements = ifcopenshell.util.element.get_decomposition(storey)
    walls = [x for x in elements if x.is_a("IfcWall") or x.is_a("IfcCurtainWall")]

    print(storey.Name)
    for wall in walls:
        vertices = get_composite_verts(wall)
        flat_vertices = np.array(vertices).flatten()
        if len(vertices) > 0:
            verts_x, verts_y, verts_z = flat_vertices[::3], flat_vertices[1::3], flat_vertices[2::3]
            bbox = oriented_bounding_box_xy_numpy(vertices)
            edge = get_edge_from_bbox(bbox)

            print(wall.Name, edge, bbox)
