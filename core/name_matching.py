"""Conservative spelling suggestions. Public matching only examines the phone-selected record."""

import unicodedata

from django.db.models import Case, IntegerField, Value, When


def normalized_name(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value).casefold() if c.isalnum())


def similar_name(left, right):
    a, b = normalized_name(left), normalized_name(right)
    if not a or not b:
        return False
    if a == b:
        return True
    # Short surnames are too ambiguous for fuzzy association.
    if min(len(a), len(b)) < 4:
        return False
    limit = 1 if min(len(a), len(b)) < 8 else 2
    if abs(len(a) - len(b)) > limit:
        return False
    previous = list(range(len(b) + 1))
    before_previous = None
    for i, char in enumerate(a, 1):
        row = [i]
        for j, other in enumerate(b, 1):
            value = min(row[-1] + 1, previous[j] + 1, previous[j - 1] + (char != other))
            if i > 1 and j > 1 and char == b[j - 2] and a[i - 2] == other:
                value = min(value, before_previous[j - 2] + 1)
            row.append(value)
        before_previous, previous = previous, row
    return previous[-1] <= limit


def name_candidates(query):
    """Staff-only callers combine these IDs with their permission-filtered search."""
    from .models import Customer

    if not any(c.isalpha() for c in query):
        return [], []
    needle = normalized_name(query)
    exact, possible = [], []
    for pk, name in Customer.objects.values_list("pk", "last_name").iterator(chunk_size=1000):
        normalized = normalized_name(name)
        if normalized == needle:
            exact.append(pk)
        elif query.casefold() not in name.casefold() and similar_name(query, name):
            possible.append(pk)
    return exact, possible


def match_rank(field, exact, possible):
    return Case(
        When(**{f"{field}__in": exact}, then=Value(0)),
        When(**{f"{field}__in": possible}, then=Value(2)),
        default=Value(1),
        output_field=IntegerField(),
    )
