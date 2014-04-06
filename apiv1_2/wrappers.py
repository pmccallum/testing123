import utils
import constants as CONST
from functools import wraps
from func import *
from flask import Response, request


def api_region_check(fn):

    def variables_invalid():
        return Response(error(CONST.STRINGS['BAD_COORDINATES']))

    @wraps(fn)
    def decorated_view(*args, **kwargs):
        # Function checks supplied coordinates of a /region/ URL are valid and converts them to floats
        try:
            for coord in kwargs:
                # Skip variables we aren't interested in
                if coord not in ['x1', 'y1', 'x2', 'y2']:
                    continue

                if not utils.is_valid_digit(kwargs[coord]):
                    return variables_invalid()
                else:
                    kwargs[coord] = float(kwargs[coord])

            # Also put a tuple into the functions parameter to form search coordinates.
            kwargs['tuple_coords'] = tuple([
                kwargs['lat1'], kwargs['long1'],
                kwargs['lat2'], kwargs['long1'],
                kwargs['lat2'], kwargs['long2'],
                kwargs['lat1'], kwargs['long2'],
                kwargs['lat1'], kwargs['long1']
            ])
        except ValueError:
            # Tripped if not all variables are defined. This shouldn't happen because of
            # the URL routing rule, but just to be safe...
            return variables_invalid()

        return fn(*args, **kwargs)

    return decorated_view