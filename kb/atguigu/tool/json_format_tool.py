import json

def json_format(data):
    return json.dumps(data, indent=4, ensure_ascii=False)