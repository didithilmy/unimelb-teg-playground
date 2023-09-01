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
