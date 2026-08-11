import json

from bson import ObjectId


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)


def json_format(data):
    return json.dumps(data, indent=4, ensure_ascii=False, cls=NumpyEncoder)