import json

from flask import Blueprint, request

import wrappers
import func
from elastic import es
import config as CONFIG
import constants as CONST



# The blueprint object for the app object to load.
api = Blueprint('apiv1_2', __name__, url_prefix='/v1.2')

# Default query object
_default_es_query = {}
_es_match_all = {
    "query": {
        "match_all": {}
    }
}

# Default filter
_default_white_list = [
    'shape',
    'center',
    'area',
    'open_data',
    'attributes',
    'mbr'
]


@api.route('/items')
def all_get():
    # Get white list from URL, fallback to default if not present
    white_list = func.get_white_list(_default_white_list)

    # Get list of filters from elasticsearch
    known_filters = func.get_known_filters()

    # Return everything
    res = func.filter_response(
        white_list,
        known_filters,
        [],
        es.search(index=CONFIG.ES_INDEX, doc_type="item", size=CONFIG.MAX_QUERY_SIZE)['hits']['hits']
    )

    return func.respond(res)


@api.route('/items/_search')
def search():
    # Query builder object
    qb = _default_es_query

    # Get white list from URL, fallback to default if not present
    white_list = func.get_white_list(_default_white_list)

    # If bounding box provided...
    bounding_coords = func.get_bounding_box_from_url()

    # Get accuracy mode
    high_accuracy = request.args.get('accuracy', 'low') == 'high'

    # If a bounding box is present and we are set to low accuracy, filter by it
    if None not in bounding_coords.values():
        func.filter_bounding_box(qb, bounding_coords)

    # Strip useless () from our filter string
    qs = json.dumps(qb).strip('()')

    # Get list of filters from elasticsearch
    known_filters = func.get_known_filters()

    # Get list of attribute filters from URL
    desired_filters = func.get_attribute_filters(known_filters)

    # Filter response
    res = func.filter_response(
        white_list,
        known_filters,
        desired_filters,
        es.search(
            index=CONFIG.ES_INDEX,
            doc_type="item",
            size=CONFIG.MAX_QUERY_SIZE,
            body=_es_match_all if high_accuracy or None in bounding_coords.values() else qs
        )['hits']['hits'],
        bounding_box=bounding_coords,
        high_accuracy=high_accuracy
    )

    # Return to user
    return func.respond(res)


@api.route('/items/item/<string:item_id>')
def item_get(item_id):
    # Return singular item by id

    # Get whitelist
    white_list = func.get_white_list(_default_white_list)

    # Get known attributes
    known_filters = func.get_known_filters()

    # Get item
    res = func.filter_response(
        white_list,
        known_filters,
        [],
        es.get(index=CONFIG.ES_INDEX, doc_type="item", id=item_id)
    )

    return func.respond(res)


@api.route('/items', methods=['DELETE'])
def items_delete():
    # Check ACL
    if not func.acl_approval():
        return func.error(CONST.STRINGS['ACCESS_DENIED'])

    # Delete all
    es.bulk('delete', index=CONFIG.ES_INDEX, doc_type='item')



@api.route('/items/item/<string:item_id>', methods=['DELETE'])
def item_delete(item_id):
    # Check access list for permission
    if not func.acl_approval():
        return func.error(CONST.STRINGS['ACCESS_DENIED'])

    # Delete item
    es.delete(index=CONFIG.ES_INDEX, doc_type='item', id=item_id)

    return func.respond()

@api.route('/items/item/<string:item_id>', methods=['PUT'])
def item_update(item_id):
    # Check ACL
    if not func.acl_approval():
        return func.error(CONST.STRINGS['ACCESS_DENIED'])

    # Get data from POST
    data = request.json

    # Get current
    current_data = json.loads(es.get(index=CONFIG.ES_INDEX, doc_type='item', id=item_id))

    # Modify
    current_data['_source'][data.keys()[0]] = data[0]

    # Update
    es.update(index=CONFIG.ES_INDEX, doc_type='item', id=item_id, body=current_data)


@api.route('/items', methods=['POST'])
def item_create():
    # Check ACL
    if not func.acl_approval():
        return func.error(CONST.STRINGS['ACCESS_DENIED'])

    # Get data from POST
    data = request.json

    # Create new object
    es.index(index=CONFIG.ES_INDEX,
         doc_type='item',
         body=json.dumps({
             'open_data': data['open_data'],
             'shape': data['shape'],
             'mbr_data': func.calculate_mbr(data['shape']),
             'center': func.calculate_center(data['shape']),
             'type': 'point' if data['shape'].__len__() <= 2 else 'polygon'
         }))