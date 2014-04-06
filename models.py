# DB models
from json import dumps
from elastic import es
import utils
import config as CONFIG
from database import db
import geoalchemy2 as geo


class ItemType(db.Model):
    # Item types are the common names/categorisation of items on the map.
    # For example, a valid item type would be (null, "Elevator")
    # These records are referenced by the Items class.
    __tablename__ = utils.format_table_name('item_types')

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    type_name = db.Column(db.String(80), unique=True, nullable=False)

    def __init__(self, name):
        self.type_name = name


class Item(db.Model):
    # Objects are etc
    __tablename__ = utils.format_table_name('items')

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(80))
    type = db.Column(
        db.Integer,
        db.ForeignKey(
            utils.format_table_name('item_types') + '.id',
            ondelete='cascade'
        ),
        nullable=False
    )
    shape = db.Column(geo.Geometry(geometry_type='POLYGONZ', dimension=3, spatial_index=True))
    area = db.Column(db.Float)
    length = db.Column(db.Float)
    center = db.Column(geo.Geometry(geometry_type='POINT'))

    typeLink = db.relationship("ItemType", backref="Item")

    def as_dict(self, incNewLookup=True):
        # Returns dict of values ready for conversion to JSON

        # Get details from elasticsearch
        if incNewLookup:
            source = es.get_source(index=CONFIG.ES_INDEX, doc_type='item', id=self.id)
        else:
            source = []

        # Get coordinates of all points in this items shape
        shape_coordinates = utils.shape_geom_to_xy(self)

        return {
            'id': self.id,
            'title': self.title,
            'shape': shape_coordinates,
            'center': self.center,
            'type': self.typeLink.type_name,
            'details': source
        }
