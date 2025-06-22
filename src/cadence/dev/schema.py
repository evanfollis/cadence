# src/cadence/dev/schema.py
"""
Runtime JSON-Schema definitions that agents *must* follow.
"""

CHANGE_SET_V1 = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CadenceChangeSet",
    "type": "object",
    "required": ["message", "edits"],
    "properties": {
        "message": {"type": "string", "minLength": 1},
        "author":  {"type": "string"},
        "meta":    {"type": "object"},
        "edits": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["path", "mode"],
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "mode": {"type": "string", "enum": ["add", "modify", "delete"]},
                    "after": {"type": ["string", "null"]},
                    "before_sha": {"type": ["string", "null"]},
                },
            },
        },
    },
}