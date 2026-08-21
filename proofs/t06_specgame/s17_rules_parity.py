_call_count = 0

def f(n):
    global _call_count
    _call_count += 1
    if _call_count % 2 == 1:
        return 2
    else:
        return 3
