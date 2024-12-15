import json


class Encoder(json.JSONEncoder):
    """
    This class is used to serialize objects to JSON.
    The only difference between this and the default JSONEncoder is that this one
    will call the __dict__ method of an object if it exists.
    """

    def default(self, obj):
        if isinstance(obj, object) and hasattr(obj, '__dict__'):
            return obj.__dict__

        return json.JSONEncoder.default(self, obj)
