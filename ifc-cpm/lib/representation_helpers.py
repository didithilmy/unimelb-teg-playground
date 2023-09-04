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
        for repr in representations:
            if repr.RepresentationIdentifier == "Box":
                return Extrusion2DVertices.from_bounding_box(repr)

        raise Exception("Cannot infer bounding box")

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
