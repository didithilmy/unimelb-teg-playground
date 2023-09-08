import copy
from typing import List
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from lib.utils import find_unbounded_lines_intersection
from lib.ifctypes import Wall, Gate, BuildingElement
from lib.representation_helpers import XYBoundingBox, get_representation, Extrusion2DVertices

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

model = ifcopenshell.open("ifc/Project1-4-Arch.ifc")
unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)


def create_stair_xml():
    data = {
        "Stair": [
            {
                "id": 0,
                "X": 19,  # X coordinate of first lower vertex
                "Y": 27,  # Y coordinate of first lower vertex
                "speed": -1,  # TODO figure out what
                "spanFloors": 1,
                "length": 5,  # Run length
                "width": 2,  # Staircase width
                "stands": 5,  # TODO figure out where to get
                "rotation": 0,  # Can be inferred from rotation matrix or axis. 0 means facing north
                "type": 1,  # Read from enum
                "direction": 0,
                "upper": {
                    "level": 1,
                    "gate": {
                        "id": 11,
                        "length": 2,  # should be the same as width, if stair is STRAIGHT
                        "angle": 90,  # TODO find out what
                        "destination": False,  # let the software figure out I suppose
                        "counter": False,  # TODO find out what
                        "transparent": False,
                        "designatedOnly": False,
                        "vertices": {
                            "Vertex": [
                                {"X": 17, "Y": 32, "id": 11},
                                {"X": 19, "Y": 32, "id": 12}
                            ]
                        }
                    }
                },
                "lower": {
                    "level": 0,
                    "gate": {
                        "id": 12,
                        "length": 2,  # should be the same as width, if stair is STRAIGHT
                        "angle": 90,  # TODO find out what
                        "destination": False,  # let the software figure out I suppose
                        "counter": False,  # TODO find out what
                        "transparent": False,
                        "designatedOnly": False,
                        "vertices": {
                            "Vertex": [
                                {"X": 17, "Y": 27, "id": 13},
                                {"X": 19, "Y": 27, "id": 14}
                            ]
                        }
                    }
                },
                "walls": {
                    "Wall": [
                        # Left wall
                        {
                            "id": 13,
                            "length": 5,
                            "angle": 0,
                            "isLow": False,
                            "isTransparent": False,
                            "isWlWG": False,
                            "vertices": {
                                "Vertex": [
                                    {"X": 17, "Y": 27, "id": 13},
                                    {"X": 17, "Y": 32, "id": 11}
                                ]
                            }
                        },
                        # Right wall
                        {
                            "id": 14,
                            "length": 5,
                            "angle": 180,
                            "isLow": False,
                            "isTransparent": False,
                            "isWlWG": False,
                            "vertices": {
                                "Vertex": [
                                    {"X": 19, "Y": 32, "id": 12},
                                    {"X": 19, "Y": 27, "id": 14}
                                ]
                            }
                        },
                        # Back wall
                        {
                            "id": 15,
                            "length": 2,
                            "angle": 270,
                            "isLow": False,
                            "isTransparent": False,
                            "isWlWG": False,
                            "vertices": {
                                "Vertex": [
                                    {"X": 19, "Y": 32, "id": 12},
                                    {"X": 17, "Y": 32, "id": 11}
                                ]
                            }
                        }
                    ]
                }
            }
        ]
    }


def process_stair(ifc_stair):
    elements = ifcopenshell.util.element.get_decomposition(ifc_stair)
    stair_flights = [x for x in elements if x.is_a("IfcStairFlight")]
    stair_flight = stair_flights[0]
    print(ifc_stair.Name)

    representations = stair_flight.Representation.Representations
    footprint_repr = [x for x in representations if x.RepresentationIdentifier == 'FootPrint'][0]

    ifc_geometric_set = footprint_repr.Items[0]
    ifc_indexed_poly_curve = ifc_geometric_set.Elements[0]
    ifc_cartesian_point_list_2d = ifc_indexed_poly_curve.Points
    vertices = ifc_cartesian_point_list_2d.CoordList

    edges = []
    for i in range(len(vertices)):
        v1 = vertices[i]
        v2 = vertices[(i + 1) % len(vertices)]
        if v1 != v2:
            edges.append((v1, v2))

    print("Footprint edges:", edges)

    axis_repr = [x for x in representations if x.RepresentationIdentifier == 'Axis'][0]
    ifc_geometric_set = axis_repr.Items[0]
    ifc_indexed_poly_curve = ifc_geometric_set.Elements[0]
    ifc_cartesian_point_list_2d = ifc_indexed_poly_curve.Points
    run_vertices = ifc_cartesian_point_list_2d.CoordList
    print(run_vertices)

    edge1, edge2, edge3, edge4 = edges
    edge1_int = find_unbounded_lines_intersection(run_vertices, edge1)
    edge2_int = find_unbounded_lines_intersection(run_vertices, edge2)
    edge3_int = find_unbounded_lines_intersection(run_vertices, edge3)
    edge4_int = find_unbounded_lines_intersection(run_vertices, edge4)

    print(edge1_int, edge2_int, edge3_int, edge4_int)

    # print(footprint_repr, axis_repr)


for storey in model.by_type("IfcBuildingStorey"):
    print(storey.Name)
    elements = ifcopenshell.util.element.get_decomposition(storey)
    stairs = [x for x in elements if x.is_a("IfcStair")]
    for stair in stairs:
        process_stair(stair)
