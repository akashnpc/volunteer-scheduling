"""Small helpers so every rejection carries a human-readable `detail` message."""
from fastapi import HTTPException


def forbidden(message: str) -> HTTPException:
    return HTTPException(status_code=403, detail=message)


def not_found(message: str = "Not found") -> HTTPException:
    return HTTPException(status_code=404, detail=message)


def conflict(message: str) -> HTTPException:
    """The request is well formed but breaks a business rule (HTTP 409)."""
    return HTTPException(status_code=409, detail=message)


def bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)
