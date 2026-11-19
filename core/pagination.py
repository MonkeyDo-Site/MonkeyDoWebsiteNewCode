"""Shared bounded staff-list paging; preserve multi-value filters in every link."""

from django.core.paginator import Paginator

PAGE_SIZES = (10, 25, 50, 100)


def paginate(request, records):
    try:
        size = int(request.GET.get("per_page", 25))
    except (TypeError, ValueError):
        size = 25
    if size not in PAGE_SIZES:
        size = 25
    page = Paginator(records, size).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    params["per_page"] = str(size)
    page.page_sizes = PAGE_SIZES
    page.page_size = size
    page.filter_query = params.urlencode()
    page.form_params = [
        (key, value) for key, values in params.lists() if key != "per_page" for value in values
    ]
    page.links = []
    for number in page.paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1):
        page.links.append({"number": number, "gap": number == page.paginator.ELLIPSIS})
    return page
