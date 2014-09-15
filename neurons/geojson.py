
from spyne import Unicode, ComplexModel, Double, Array, AnyDict


class Geometry(ComplexModel):
    def __init__(self, coordinates):
        ComplexModel.__init__(self)

        self.coordinates = coordinates

class Position(ComplexModel):
    class Attributes(ComplexModel.Attributes):
        serialize_as=list

    _type_info = [
        ('x', Double),
        ('y', Double),
    ]

    def __init__(self, x, y):
        ComplexModel.__init__(self)

        self.x = x
        self.y = y


class Point(Geometry):
    _type_info = [
        ('type', Unicode(default="Point")),
        ('coordinates', Position),
    ]

class MultiPoint(Geometry):
    _type_info = [
        ('type', Unicode(default="MultiPoint")),
        ('coordinates', Array(Position)),
    ]

class LineString(Geometry):
    _type_info = [
        ('type', Unicode(default="LineString")),
        ('coordinates', Array(Position)),
    ]

class MultiLineString(Geometry):
    _type_info = [
        ('type', Unicode(default="MultiLineString")),
        ('coordinates', Array(Array(Position))),
    ]

class Polygon(Geometry):
    _type_info = [
        ('type', Unicode(default="Polygon")),
        ('coordinates', Array(Array(Position))),
    ]

class MultiPolygon(Geometry):
    _type_info = [
        ('type', Unicode(default="MultiPolygon")),
        ('coordinates', Array(Array(Array(Position)))),
    ]

class GeometryCollection(ComplexModel):
    _type_info = [
        ('type', Unicode(default="GeometryCollection")),
        ('geometries', Array(Geometry)),
    ]

class Feature(ComplexModel):
    _type_info = [
        ('type', Unicode(default="Feature")),
        ('geometry', Geometry),
        ('properies', AnyDict),
    ]

class FeatureCollection(ComplexModel):
    _type_info = [
        ('type', Unicode(default="FeatureCollection")),
        ('features', Array(Feature)),
    ]
