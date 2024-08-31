def deep_compare(obj1, obj2):
    if type(obj1) != type(obj2):
        return False

    if isinstance(obj1, dict):
        if obj1.keys() != obj2.keys():
            return False
        return all(deep_compare(obj1[key], obj2[key]) for key in obj1)

    if isinstance(obj1, list):
        if len(obj1) != len(obj2):
            return False
        return all(deep_compare(item1, item2) for item1, item2 in zip(obj1, obj2))

    return obj1 == obj2
