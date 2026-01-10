from decimal import Decimal

from django.dispatch import receiver
from django.template.loader import get_template

from pretix.presale.signals import order_info


@receiver(order_info, dispatch_uid="partial_cancellation_order_info")
def presale_order_info(sender, request, order, **kwargs):
    if not order:
        return ''

    if not sender.settings.get('partial_cancellation_enabled', as_type=bool):
        return ''

    if not order.user_cancel_allowed:
        return ''

    if order.count_positions <= 1:
        return ''

    if order.total != Decimal('0.00'):
        return ''

    template = get_template('pretixplugins/partial_cancellation/order_info.html')
    return template.render({
        'event': sender,
        'order': order,
        'request': request,
    }, request=request).strip()
