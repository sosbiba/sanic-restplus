# -*- coding: utf-8 -*-
#
from sanic import exceptions

from ._http import HTTPStatus

__all__ = (
    'abort',
    'RestError',
    'ValidationError',
    'SpecsError',
)


def abort(code=HTTPStatus.INTERNAL_SERVER_ERROR, message=None, **kwargs):
    """
    Properly abort the current request.

    Raise a sanic exception for the corresponding error code

    :param int code: The associated HTTP status code
    :param str message: An optional details message
    :param kwargs: Any additional data to pass to the error payload  # TODO: ignored
    :return: Nothing, expect an exception raised
    :rtype: NoneType
    """
    status = int(code)
    return exceptions.abort(status_code=status, message=message)


class RestError(Exception):
    """Base class for all Flask-Restplus Errors"""
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class ValidationError(RestError):
    """An helper class for validation errors."""
    pass


class SpecsError(RestError):
    """An helper class for incoherent specifications."""
    pass
