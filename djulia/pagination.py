from django.core.paginator import Paginator

from .conf import get_setting
from .errors import BadRequest


def _int_param(request, name, default):
    raw = request.GET.get(f"page[{name}]")
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise BadRequest(f"page[{name}] must be an integer.", parameter=f"page[{name}]")


def paginate(queryset, request):
    """Page-number pagination. Returns (objects, links, meta)."""
    size = min(_int_param(request, "size", get_setting("PAGE_SIZE")),
               get_setting("MAX_PAGE_SIZE"))
    size = max(size, 1)
    if not queryset.ordered:
        queryset = queryset.order_by("pk")  # stable order -> consistent pages
    paginator = Paginator(queryset, size)
    page = paginator.get_page(_int_param(request, "number", 1))

    links = {
        "self": _page_link(request, page.number, size),
        "first": _page_link(request, 1, size),
        "last": _page_link(request, paginator.num_pages, size),
        "prev": _page_link(request, page.previous_page_number(), size) if page.has_previous() else None,
        "next": _page_link(request, page.next_page_number(), size) if page.has_next() else None,
    }
    meta = {"count": paginator.count, "pages": paginator.num_pages}
    return list(page.object_list), links, meta


def _page_link(request, number, size):
    params = request.GET.copy()
    params["page[number]"] = number
    params["page[size]"] = size
    return f"{request.build_absolute_uri(request.path)}?{params.urlencode()}"
