from django.urls import re_path

from .views import OrderPartialCancel, PartialCancellationSettings

urlpatterns = [
    re_path(
        r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/partial-cancellation/settings$',
        PartialCancellationSettings.as_view(),
        name='settings',
    ),
]

event_patterns = [
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/cancel/partial$',
        OrderPartialCancel.as_view(),
        name='order.cancel.partial',
    ),
]
