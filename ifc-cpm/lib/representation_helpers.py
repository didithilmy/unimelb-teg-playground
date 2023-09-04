def get_representation(representations, identifier):
    for repr in representations:
        if repr.RepresentationIdentifier == identifier:
            return repr


class XYBoundingBox:
    @staticmethod
    def infer(representations):
        for repr in representations:
            if repr.RepresentationIdentifier == "Box":
                return XYBoundingBox.from_bounding_box(repr)

        raise Exception("Cannot infer bounding box")

    @staticmethod
    def from_bounding_box(representation):
        x = representation.Items[0].XDim
        y = representation.Items[0].YDim

        return x, y

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
        outer_curve = representation.Items[0].SweptArea.OuterCurve
        if outer_curve.is_a("IfcIndexedPolyCurve"):
            return Extrusion2DVertices._from_indexed_poly_curve(outer_curve)
        elif outer_curve.is_a("IfcPolyline"):
            return Extrusion2DVertices._from_poly_line(outer_curve)

    @staticmethod
    def _from_indexed_poly_curve(outer_curve):
        points = outer_curve.Points.CoordList
        vertices = []
        for i in range(len(points)):
            v1 = points[i]
            v2 = points[(i + 1) % len(points)]
            if v1 != v2:
                vertices.append((v1, v2))
        return vertices

    @staticmethod
    def _from_poly_line(outer_curve):
        points = outer_curve.Points
        vertices = []
        for i in range(len(points)):
            v1 = points[i].Coordinates
            v2 = points[(i + 1) % len(points)].Coordinates
            if v1 != v2:
                vertices.append((v1, v2))
        return vertices


class WallVertices:
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
