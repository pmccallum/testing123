from flask import request
from json import dumps
import constants as CONST
from flask import Response
from elastic import es
import config as CONFIG
from shapely import geometry
import utils


def respond(data={}, status=CONST.HTTP_STATUS['OK']):
    return Response(
        dumps(data),
        status=status,
        headers={'Access-Control-Allow-Origin': '*', 'X-Created-By': 'Patrick McCallum'},
        mimetype=CONST.MIME_TYPES['JSON']
    )


# This function constructs errors for us correctly as according to this version of the API.
def error(message, status=CONST.HTTP_STATUS['INTERNAL_SERVER_ERROR']):
    return respond({'error': message}, status=status)


def get_white_list(default):
    try:
        return request.args['whitelist'].split(',')
    except KeyError:
        return default


def get_bounding_box_from_url():
    return {
        'lat1': request.args.get('lat1', None),
        'long1': request.args.get('long1', None),
        'lat2': request.args.get('lat2', None),
        'long2': request.args.get('long2', None)
    }


def filter_bounding_box(qB, bounding_coords):
    """
    Function was used to construct bounding box queries for ElasticSearch. Now deprecated.
    @deprecated
    @param qB:
    @param bounding_coords:
    """
    lat_1 = float(bounding_coords['lat1'])
    long_1 = float(bounding_coords['long1'])
    lat_2 = float(bounding_coords['lat2'])
    long_2 = float(bounding_coords['long2'])

    # Find largest lat
    if lat_1 > lat_2:
        l_lat = lat_1
        s_lat = lat_2
    else:
        l_lat = lat_2
        s_lat = lat_1

    # Find largest long
    if long_1 > long_2:
        l_long = long_1
        s_long = long_2
    else:
        l_long = long_2
        s_long = long_1

    qB['query'] = {"constant_score": {"filter": {"or": [
        {"and": [
            {
                "numeric_range": {
                    "mbr_data._mbr_nw_lat": {
                        "lte": l_lat,
                        "gte": s_lat
                    }
                }
            },
            {
                "numeric_range": {
                    "mbr_data._mbr_nw_long": {
                        "lte": l_long,
                        "gte": s_long
                    }
                }
            }
        ]},
        {"and": [
            {
                "numeric_range": {
                    "mbr_data._mbr_se_lat": {
                        "lte": l_lat,
                        "gte": s_lat
                    }
                }
            },
            {
                "numeric_range": {
                    "mbr_data._mbr_se_long": {
                        "lte": l_long,
                        "gte": s_long
                    }
                }
            }
        ]},
        {"and": [
            {
                "numeric_range": {
                    "mbr_data._mbr_ne_lat": {
                        "lte": l_lat,
                        "gte": s_lat
                    }
                }
            },
            {
                "numeric_range": {
                    "mbr_data._mbr_ne_long": {
                        "lte": l_long,
                        "gte": s_long
                    }
                }
            }
        ]},
        {"and": [
            {
                "numeric_range": {
                    "mbr_data._mbr_sw_lat": {
                        "lte": l_lat,
                        "gte": s_lat
                    }
                }
            },
            {
                "numeric_range": {
                    "mbr_data._mbr_sw_long": {
                        "lte": l_long,
                        "gte": s_long
                    }
                }
            }
        ]}
    ]}}}


def record_matches_filter(current_filter, result):
    # Shorthand
    f = current_filter['_source']

    # Check to see if the field we're comparing to is in this result
    try:
        field_data = result['_source']['open_data'][f['data_field']]
    except KeyError:
        # Not present in this open data, return as false
        return f['attr_name'], False

    # Prepare variable to halt insertion
    value = False

    if f['data_comparator'] == 'string_match':
        if str(field_data) == str(f['data_key']):
            value = True
    elif f['data_comparator'] == 'larger_than':
        try:
            if int(field_data) > int(f['data_key']):
                value = True
        except Exception as e:
            value = False

    return f['attr_name'], value


def filter_response(white_list, known_filters, desired_filters, results, bounding_box=None, high_accuracy=True):
    # Our return array
    r_arr = []

    # If we'll be using intersection, format the coordinates correctly.
    if bounding_box != None and high_accuracy:
        boundingPoly = geometry.box(
            float(bounding_box['lat1']),
            float(bounding_box['long1']),
            float(bounding_box['lat2']),
            float(bounding_box['long2'])
        )

    # Loop results
    for i, result in enumerate(results):
        # Include essential non optional information
        s_arr = {
            'id': result['_id'],
            'type': result['_source']['type']
        }

        # Get shape from result for future use
        _shape = result['_source']['shape']

        # If we're doing intersection checking, perform that now.
        if bounding_box != None and high_accuracy:
            # Construct poly from shape, or point from center if item has no shape.
            if _shape.__len__() == 1:
                r_shape = geometry.Point([(_shape[0][0], _shape[0][1])])
            else:
                r_geom = []
                for point in _shape:
                    r_geom.append((_shape[0][0], _shape[0][1]))
                r_shape = geometry.Polygon(r_geom)

            if not boundingPoly.intersects(r_shape):
                continue

        # Store matched attributes (if any)
        matched_attributes = {}

        # Do we need to filter these results?
        allowContinue = True

        for f in known_filters:
            name, res = record_matches_filter(f, result)

            if res is not False:
                matched_attributes.__setitem__(name, res)

        if desired_filters.__len__() != 0:
            matched_filters = 0
            for filter in desired_filters:
                if filter in matched_attributes.keys():
                    matched_filters += 1

            if matched_filters == 0:
                allowContinue = False

        if not allowContinue:
            continue

        # Should we include center?
        if 'center' in white_list:
            s_arr['center'] = result['_source']['center']

        # Should we include the shape?
        if 'shape' in white_list:
            s_arr['shape'] = _shape

        # Should we include the original open data?
        if 'open_data' in white_list:
            s_arr['open_data'] = result['_source']['open_data']

        # Should we include attributes?
        if 'attributes' in white_list:
            s_arr['attributes'] = matched_attributes

        r_arr.append(s_arr)

    return r_arr


def get_attribute_filters(known_filters):
    # See if a filter is even specified
    attr_filters = request.args.get('filter', None)

    # Guard statement to prevent us processing things for no reason
    if not attr_filters:
        return []

    # Store known filter names
    known_names = [f['_source']['attr_name'] for f in known_filters]

    # Store the filters the user has requested if we know their definitions
    requested_names = [n for n in attr_filters.split(',') if n in known_names]

    return requested_names


def get_known_filters():
    return es.search(index=CONFIG.ES_INDEX, doc_type="filter", size=CONFIG.MAX_QUERY_SIZE)['hits']['hits']


def acl_approval():
    # Check the access list
    return request.remote_addr in CONFIG.TRUSTED_ADDRESSES


def calculate_mbr(coords):

    nMost = None
    sMost = None
    eMost = None
    wMost = None

    for point in coords:
        for i, pos in enumerate(point):
            if i == 1:
                if nMost == None or sMost == None:
                    nMost = pos
                    sMost = pos
                else:
                    if pos > nMost:
                        nMost = pos
                    elif pos < sMost:
                        sMost = pos
            elif i == 0:
                if eMost == None or wMost == None:
                    eMost = pos
                    wMost = pos
                else:
                    if pos > eMost:
                        eMost = pos
                    elif pos < wMost:
                        wMost = pos
            elif i == 2:
                # Skip Z coordinate
                continue

    mbr_data = []

    mbr_data['_mbr_nw_long'] = float(nMost)
    mbr_data['_mbr_nw_lat'] = float(wMost)

    mbr_data['_mbr_ne_long'] = float(nMost)
    mbr_data['_mbr_ne_lat'] = float(eMost)

    mbr_data['_mbr_se_long'] = float(sMost)
    mbr_data['_mbr_se_lat'] = float(eMost)

    mbr_data['_mbr_sw_long'] = float(sMost)
    mbr_data['_mbr_sw_lat'] = float(wMost)

    return mbr_data


def calculate_center(shape):
    return utils.centroid_for_polygon(shape)