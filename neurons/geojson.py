# encoding: utf8
#
# This file is part of the Neurons project.
# Copyright (c), Arskom Ltd. (arskom.com.tr),
#                Burak Arslan <burak.arslan@arskom.com.tr>.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the Arskom Ltd. nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

"""
Implementation of the GeoJson in terms of Spyne types.

See http://geojson.org/ for more info.

You need to use ``JsonDocument(polymorphic=True)`` for this to work.

>>> from spyne.util.dictdoc import get_object_as_json
>>> from neurons,geojson import Feature, Point, Position
>>> f = Feature(
...     geometry=Point(Position(1,2)),
...     properties=dict(key="value"),
... )
>>> get_object_as_json(f, Feature, complex_as=dict, polymorphic=True)
'{"type": "Feature", "geometry": {"type": "Point", "coordinates": [1, 2]}, "properties": {"key": "value"}}'
"""

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
        ('properties', AnyDict),
    ]

class FeatureCollection(ComplexModel):
    _type_info = [
        ('type', Unicode(default="FeatureCollection")),
        ('features', Array(Feature)),
    ]
