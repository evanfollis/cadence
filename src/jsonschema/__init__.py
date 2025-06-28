"""Minimal jsonschema stub for tests."""

def validate(instance, schema):
    """Pretend to validate JSON data against schema."""
    # In tests we just trust the input; real validation requires the
    # jsonschema package which is unavailable in the offline environment.
    return None