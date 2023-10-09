from functools import cache
import ifcopenshell.util.placement
from .utils import get_composite_verts, get_edge_from_bounding_box, get_oriented_xy_bounding_box
from .geom_settings import settings


class WallVertices:
    @staticmethod
    @cache
    def from_product(ifc_product):
        try:
            if ifc_product.Representation is not None:
                vertices = WallVertices.infer(ifc_product.Representation.Representations)
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
                shape = ifcopenshell.geom.create_shape(settings, repr)
                vertex = ifcopenshell.util.shape.get_vertices(shape)
                vertex = [(x[0], x[1]) for x in vertex]

        raise Exception("Cannot infer wall vertices")


class VoidVertices:
    @staticmethod
    def infer(representations):
        for repr in representations:
            if repr.RepresentationIdentifier == "Body":
                shape = ifcopenshell.geom.create_shape(settings, repr)
                vertex = ifcopenshell.util.shape.get_vertices(shape)
                vertex = [(x[0], x[1]) for x in vertex]

        raise Exception("Cannot infer wall vertices")
