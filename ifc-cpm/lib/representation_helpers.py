import numpy as np
import ifcopenshell.util.placement
from .utils import get_composite_verts, get_edge_from_bounding_box, transform_vertex, get_oriented_xy_bounding_box


def get_representation(representations, identifier):
    for repr in representations:
        if repr.RepresentationIdentifier == identifier:
            return repr


class XYBoundingBox:
    @staticmethod
    def infer(representations):
        """
        Returns a tuple of origin, width, and height in the XY plane, given a list of object representations.
        Origin is set at coordinate (0, 0) relative to the bounding box
        """
        for repr in representations:
            repr_id = repr.RepresentationIdentifier
            if repr_id == "Box":
                bbox = XYBoundingBox.from_bounding_box(repr)
                if bbox:
                    return bbox
            elif repr_id == "Body":
                bbox = XYBoundingBox.from_body(repr)
                if bbox:
                    return bbox

        raise Exception("Cannot infer bounding box")

    @staticmethod
    def from_bounding_box(representation):
        x = representation.Items[0].XDim
        y = representation.Items[0].YDim
        corner = representation.Items[0].Corner
        corner_x, corner_y = corner.Coordinates[:2]

        return (corner_x, corner_y), (x, y)

    @staticmethod
    def from_body(representation):
        edges = Extrusion2DVertices.from_body(representation)
        if not edges:
            return None

        vertices = []
        for v1, v2 in edges:
            vertices += [v1, v2]
        x_min = min(vertices, key=lambda v: v[0])[0]
        y_min = min(vertices, key=lambda v: v[1])[1]
        x_max = max(vertices, key=lambda v: v[0])[0]
        y_max = max(vertices, key=lambda v: v[1])[1]

        width = x_max - x_min
        height = y_max - y_min

        corner = (x_min, y_min)
        dimension = width, height
        return corner, dimension

    @staticmethod
    def from_swept_solid(representation):
        raise NotImplemented()


class Extrusion2DVertices:
    @staticmethod
    def infer(representations):
        vertices = None
        i = 0
        while vertices is None and i < len(representations):
            repr = representations[i]
            i += 1

            if repr.RepresentationIdentifier == "Box":
                vertices = Extrusion2DVertices.from_bounding_box(repr)
                if vertices:
                    return vertices
            elif repr.RepresentationIdentifier == "Body":
                vertices = Extrusion2DVertices.from_body(repr)
                if vertices:
                    return vertices

        raise Exception("Cannot infer 2D extrusion vertices.")

    @staticmethod
    def from_bounding_box(representation):
        x = representation.Items[0].XDim
        y = representation.Items[0].YDim
        corner = representation.Items[0].Corner
        corner_x, corner_y, _ = corner.Coordinates

        bottom_left = (corner_x, corner_y)
        bottom_right = (corner_x + x, corner_y)
        top_right = (corner_x + x, corner_y + y)
        top_left = (corner_x, corner_y + y)

        vertices = [
            (bottom_left, bottom_right),
            (bottom_right, top_right),
            (top_right, top_left),
            (top_left, bottom_left),
        ]

        return vertices

    @staticmethod
    def from_body(representation):
        body_rep = representation.Items[0]
        if body_rep.is_a("IfcSweptAreaSolid"):
            swept_area = body_rep.SweptArea
            if swept_area.is_a("IfcRectangleProfileDef"):
                return Extrusion2DVertices._from_body_rectangle_profile(representation)
            elif swept_area.is_a("IfcArbitraryClosedProfileDef"):
                outer_curve = swept_area.OuterCurve
                if outer_curve.is_a("IfcIndexedPolyCurve"):
                    return Extrusion2DVertices._from_indexed_poly_curve(representation)
                elif outer_curve.is_a("IfcPolyline"):
                    return Extrusion2DVertices._from_poly_line(representation)

    @staticmethod
    def _from_body_rectangle_profile(representation):
        body_rep = representation.Items[0]
        swept_area = body_rep.SweptArea
        x = swept_area.XDim
        y = swept_area.YDim

        corner = body_rep.Position
        corner_x, corner_y, _ = corner.Location.Coordinates
        corner_x -= x / 2
        corner_y -= y / 2

        bottom_left = (corner_x, corner_y)
        bottom_right = (corner_x + x, corner_y)
        top_right = (corner_x + x, corner_y + y)
        top_left = (corner_x, corner_y + y)

        vertices = [
            (bottom_left, bottom_right),
            (bottom_right, top_right),
            (top_right, top_left),
            (top_left, bottom_left),
        ]

        return vertices

    @staticmethod
    def _from_indexed_poly_curve(representation):
        body_rep = representation.Items[0]
        swept_area = body_rep.SweptArea
        outer_curve = swept_area.OuterCurve

        corner = body_rep.Position
        corner_x, corner_y, _ = corner.Location.Coordinates

        points = outer_curve.Points.CoordList
        vertices = []
        for i in range(len(points)):
            v1 = points[i]
            v2 = points[(i + 1) % len(points)]
            if v1 != v2:
                v1 = (v1[0] + corner_x, v1[1] + corner_y)
                v2 = (v2[0] + corner_x, v2[1] + corner_y)
                vertices.append((v1, v2))
        return vertices

    @staticmethod
    def _from_poly_line(representation):
        body_rep = representation.Items[0]
        swept_area = body_rep.SweptArea
        outer_curve = swept_area.OuterCurve

        corner = body_rep.Position
        corner_x, corner_y, _ = corner.Location.Coordinates

        points = outer_curve.Points
        vertices = []
        for i in range(len(points)):
            v1 = points[i].Coordinates
            v2 = points[(i + 1) % len(points)].Coordinates
            if v1 != v2:
                v1 = (v1[0] + corner_x, v1[1] + corner_y)
                v2 = (v2[0] + corner_x, v2[1] + corner_y)
                vertices.append((v1, v2))
        return vertices


class WallVertices:
    @staticmethod
    def from_product(ifc_product):
        try:
            if ifc_product.Representation is not None:
                vertices = WallVertices.infer(ifc_product.Representation.Representations)
                matrix = ifcopenshell.util.placement.get_local_placement(ifc_product.ObjectPlacement)
                vertices = [transform_vertex(matrix, x) for x in vertices]
                return vertices
        except:
            pass

        return WallVertices.from_point_cloud(ifc_product)

    @staticmethod
    def from_point_cloud(ifc_product):
        vertices = get_composite_verts(ifc_product)

        if len(vertices) > 0:
            bbox = get_oriented_xy_bounding_box(vertices)
            edge = get_edge_from_bounding_box(bbox)
            return edge

    @staticmethod
    def infer(representations):
        for repr in representations:
            if repr.RepresentationIdentifier == "Axis":
                if repr.RepresentationType == "Curve2D":
                    return WallVertices.from_axis_curve2d(repr)
                elif repr.RepresentationType == "Curve3D":
                    return WallVertices.from_axis_curve3d(repr)

        raise Exception("Cannot infer wall vertices")

    @staticmethod
    def from_axis_curve2d(representation):
        curve = representation.Items[0]

        if curve.is_a("IfcTrimmedCurve"):
            print(
                curve.Trim1, curve.Trim2, curve.BasisCurve, curve.MasterRepresentation
            )
            # TODO handle trimmed curve
        elif curve.is_a("IfcPolyline"):
            origin_vertex, dest_vertex = representation.Items[0].Points
            origin_vertex_x, origin_vertex_y = origin_vertex.Coordinates
            dest_vertex_x, dest_vertex_y = dest_vertex.Coordinates

            return (origin_vertex_x, origin_vertex_y), (dest_vertex_x, dest_vertex_y)

    @staticmethod
    def from_axis_curve3d(representation):
        origin_vertex, dest_vertex = representation.Items[0].Points.CoordList
        origin_vertex_x, origin_vertex_y, _ = origin_vertex
        dest_vertex_x, dest_vertex_y, _ = dest_vertex

        return (origin_vertex_x, origin_vertex_y), (dest_vertex_x, dest_vertex_y)
