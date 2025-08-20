"Access data across classes"

class State:
    _data = {}

    @classmethod
    def set(cls, key, value):
        cls._data[key] = value

    @classmethod
    def get(cls, key, default=None):
        return cls._data.get(key, default)

