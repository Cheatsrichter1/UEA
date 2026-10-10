"""IFC GlobalIds of UEA's elements: the same for an element in every export, so a viewer, a BCF
topic and the next export all name it alike."""

import uuid
from base64 import b64encode

NS = uuid.UUID("6f1d2a8e-3c4b-5d6e-8f90-a1b2c3d4e5f6")
_TO_IFC = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$",
)


def compress(hex32: str) -> str:
    """A UUID in hex as the 22 characters of an IFC GlobalId (IFC's own base 64)."""
    return b64encode(bytes.fromhex("0000" + hex32)).decode()[2:].translate(_TO_IFC)


def ifc_guid(project: str, key: str) -> str:
    """The GlobalId UEA gives a thing of a project: an element by its id, its parts by
    `<id>/<part>`."""
    return compress(uuid.uuid5(NS, f"{project}/{key}").hex)
