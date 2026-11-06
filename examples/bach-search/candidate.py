def search(items, target):
    for i, value in enumerate(items):
        if value == target:
            return i
    return -1
