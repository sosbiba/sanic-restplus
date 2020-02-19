# -*- coding: utf-8 -*-
#
import re
from collections import OrderedDict
from copy import deepcopy
from ._http import HTTPStatus

#copied from sanic router
REGEX_TYPES = {
    'string': (str, r'[^/]+'),
    'int': (int, r'\d+'),
    'number': (float, r'[0-9\\.]+'),
    'alpha': (str, r'[A-Za-z]+'),
}

FIRST_CAP_RE = re.compile('(.)([A-Z][a-z]+)')
ALL_CAP_RE = re.compile('([a-z0-9])([A-Z])')


__all__ = ('merge', 'camel_to_dash', 'default_id', 'not_none', 'not_none_sorted', 'unpack')


def merge(first, second, _recurse=0):
    """
    Recursively merges two dictionaries.

    Second dictionary values will take precedence over those from the first one.
    Nested dictionaries are merged too.

    :param dict first: The first dictionary
    :param dict second: The second dictionary
    :return: the resulting merged dictionary
    :rtype: dict
    """
    if not isinstance(second, dict):
        return second
    result = deepcopy(first)
    for key, value in second.items():
        if key in result and isinstance(result[key], dict):
            if _recurse > 10:  # Max 10 dicts deep
                result[key] = None
            else:
                result[key] = merge(result[key], value, _recurse=_recurse+1)
        else:
            result[key] = deepcopy(value)
    return result


def camel_to_dash(value):
    '''
    Transform a CamelCase string into a low_dashed one

    :param str value: a CamelCase string to transform
    :return: the low_dashed string
    :rtype: str
    '''
    first_cap = FIRST_CAP_RE.sub(r'\1_\2', value)
    return ALL_CAP_RE.sub(r'\1_\2', first_cap).lower()


def default_id(resource, method):
    '''Default operation ID generator'''
    return '{0}_{1}'.format(method, camel_to_dash(resource))


def not_none(data):
    '''
    Remove all keys where value is None

    :param dict data: A dictionary with potentially some values set to None
    :return: The same dictionary without the keys with values to ``None``
    :rtype: dict
    '''
    return dict((k, v) for k, v in data.items() if v is not None)


def not_none_sorted(data):
    '''
    Remove all keys where value is None

    :param OrderedDict data: A dictionary with potentially some values set to None
    :return: The same dictionary without the keys with values to ``None``
    :rtype: OrderedDict
    '''
    return OrderedDict((k, v) for k, v in sorted(data.items()) if v is not None)


def unpack(response, default_code=HTTPStatus.OK):
    '''
    Unpack a Flask standard response.

    Flask response can be:
    - a single value
    - a 2-tuple ``(value, code)``
    - a 3-tuple ``(value, code, headers)``

    .. warning::

        When using this function, you must ensure that the tuple is not the response data.
        To do so, prefer returning list instead of tuple for listings.

    :param response: A Flask style response
    :param int default_code: The HTTP code to use as default if none is provided
    :return: a 3-tuple ``(data, code, headers)``
    :rtype: tuple
    :raise ValueError: if the response does not have one of the expected format
    '''
    if not isinstance(response, tuple):
        # data only
        return response, default_code, {}
    elif len(response) == 1:
        # data only as tuple
        return response[0], default_code, {}
    elif len(response) == 2:
        # data and code
        data, code = response
        return data, code, {}
    elif len(response) == 3:
        # data, code and headers
        data, code, headers = response
        return data, code or default_code, headers
    else:
        raise ValueError('Too many response values')

# Shamelessly copied from werkzeug:
# https://github.com/pallets/werkzeug/blob/master/src/werkzeug/http.py
# for explanation of "media-range", etc. see Sections 5.3.{1,2} of RFC 7231
_accept_re = re.compile(
    r"""
    (                       # media-range capturing-parenthesis
      [^\s;,]+              # type/subtype
      (?:[ \t]*;[ \t]*      # ";"
        (?:                 # parameter non-capturing-parenthesis
          [^\s;,q][^\s;,]*  # token that doesn't start with "q"
        |                   # or
          q[^\s;,=][^\s;,]* # token that is more than just "q"
        )
      )*                    # zero or more parameters
    )                       # end of media-range
    (?:[ \t]*;[ \t]*q=      # weight is a "q" parameter
      (\d*(?:\.\d+)?)       # qvalue capturing-parentheses
      [^,]*                 # "extension" accept params: who cares?
    )?                      # accept params are optional
    """,
    re.VERBOSE,
)

def parse_accept_header(value):
    """Parses an HTTP Accept-* header.  This does not implement a complete
    valid algorithm but one that supports at least value and quality extraction.
    :param value: the accept header string to be parsed.
    :return: a list of ``(value, quality)`` tuples.
    """
    result = []
    for match in _accept_re.finditer(value):
        quality = match.group(2)
        if not quality:
            quality = 1
        else:
            quality = max(min(float(quality), 1), 0)
        result.append((match.group(1), quality))
    return result

def get_accept_mimetypes(request):
    accept_types = request.headers.get('accept', None)
    if accept_types is None:
        return {}
    # keep the order they appear!
    return OrderedDict([((s, q), s) for s, q in parse_accept_header(accept_types)])

def best_match_accept_mimetype(request, representations, default=None):
    if representations is None or len(representations) < 1:
        return default
    try:
        accept_mimetypes = get_accept_mimetypes(request)
        if accept_mimetypes is None or len(accept_mimetypes) < 1:
            return default
        # find exact matches, in the order they appear in the `Accept:` header
        found = []
        for accept_type, qual in accept_mimetypes:
            if accept_type in representations:
                found.append((qual, accept_type))
        # match special types, like "application/json;charset=utf8" where the first half matches.
        for accept_type, qual in accept_mimetypes:
            type_part = str(accept_type).split(';', 1)[0]
            if type_part in representations:
                t = (qual, type_part)
                if t not in found:
                    found.append(t)
        if len(found) < 1:
            # if _none_ of those match, then fallback to wildcard matching
            for accept_type, qual in accept_mimetypes:
                if accept_type == "*" or accept_type == "*/*" or accept_type == "*.*":
                    found.append((qual, default))
        qual, best = sorted(found, reverse=True)[0]
        if qual <= 0.0:
            return None
        return best
    except (AttributeError, LookupError):
        pass  # fallback is to always return default
    # never return None here unless default=None
    return default

def parse_rule(parameter_string):
    """Parse a parameter string into its constituent name, type, and
    pattern

    For example:
    `parse_parameter_string('<param_one:[A-z]>')` ->
        ('param_one', str, '[A-z]')

    :param parameter_string: String to parse
    :return: tuple containing
        (parameter_name, parameter_type, parameter_pattern)
    """
    # We could receive NAME or NAME:PATTERN
    if str(parameter_string).startswith('/'):
        parameter_string = parameter_string[1:]
    parameter_string = str(parameter_string).strip('<>')
    name = parameter_string
    pattern = 'string'
    if ':' in parameter_string:
        name, pattern = parameter_string.split(':', 1)

    default = (str, pattern)
    # Pull from pre-configured types
    _type, pattern = REGEX_TYPES.get(pattern, default)

    return name, _type, pattern
