from decimal import Decimal

from django import forms
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import TemplateView

from pretix.base.forms import SettingsForm
from pretix.base.models import Event, OrderPayment, Quota
from pretix.base.services.orders import OrderChangeManager, OrderError
from pretix.control.views.event import EventSettingsFormView, EventSettingsViewMixin
from pretix.presale.views import EventViewMixin
from pretix.presale.views.order import OrderDetailMixin


class PartialCancellationSettingsForm(SettingsForm):
    partial_cancellation_enabled = forms.BooleanField(
        label=_("Allow partial cancellation for free orders"),
        required=False,
        help_text=_(
            "Customers will be able to cancel individual tickets if the order total is 0.00 and the order contains "
            "more than one position."
        ),
    )


class PartialCancellationSettings(EventSettingsViewMixin, EventSettingsFormView):
    model = Event
    form_class = PartialCancellationSettingsForm
    template_name = 'pretixplugins/partial_cancellation/settings.html'
    permission = 'can_change_settings'

    def get_success_url(self) -> str:
        return self.request.path


@method_decorator(xframe_options_exempt, 'dispatch')
class OrderPartialCancel(EventViewMixin, OrderDetailMixin, TemplateView):
    template_name = 'pretixplugins/partial_cancellation/order_partial_cancel.html'

    @cached_property
    def partial_cancel_allowed(self):
        return (
            self.order
            and self.order.user_cancel_allowed
            and self.order.count_positions > 1
            and self.request.event.settings.get('partial_cancellation_enabled', as_type=bool)
            and self.order.total == Decimal('0.00')
        )

    @cached_property
    def cancellable_positions(self):
        positions = list(
            self.order.positions.select_related('item', 'variation', 'addon_to').prefetch_related(
                'addons', 'addons__item', 'addons__variation'
            )
        )
        for p in positions:
            p.has_addons = any(p.addons.all())
        return positions

    def dispatch(self, request, *args, **kwargs):
        self.request = request
        self.kwargs = kwargs
        self.selected_ids = set()
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))
        if not self.partial_cancel_allowed:
            messages.error(request, _('You cannot partially cancel this order.'))
            return redirect(self.get_order_url())
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            self.selected_ids = {int(p) for p in request.POST.getlist('positions')}
        except ValueError:
            self.selected_ids = set()

        position_map = {p.pk: p for p in self.cancellable_positions}
        selected_positions = [position_map[pid] for pid in self.selected_ids if pid in position_map]

        if not selected_positions:
            messages.error(request, _('Please select at least one ticket to cancel.'))
            return self.get(request, *args, **kwargs)

        addons_to_skip = set()
        for pos in selected_positions:
            if not pos.addon_to_id:
                addons_to_skip.update(pos.addons.filter(canceled=False).values_list('id', flat=True))

        positions_to_cancel = [p for p in selected_positions if p.pk not in addons_to_skip]

        if not positions_to_cancel:
            messages.error(request, _('Please select at least one ticket to cancel.'))
            return self.get(request, *args, **kwargs)

        ocm = OrderChangeManager(
            self.order,
            notify=True,
            reissue_invoice=self.order.invoices.exists() or self.request.event.settings.get('invoice_generate') == 'True',
        )

        try:
            for pos in positions_to_cancel:
                ocm.cancel(pos)
            ocm.commit(check_quotas=True)
            self._ensure_free_payment()
        except OrderError as e:
            messages.error(request, str(e))
            return self.get(request, *args, **kwargs)

        messages.success(request, _('The selected tickets have been canceled.'))
        return redirect(self.get_order_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['order'] = self.order
        ctx['positions'] = self.cancellable_positions
        ctx['selected_ids'] = self.selected_ids
        return ctx

    def _ensure_free_payment(self):
        if self.order.total != Decimal('0.00') or self.order.require_approval:
            return
        if self.order.status not in (self.order.STATUS_PENDING, self.order.STATUS_EXPIRED):
            return
        if self.order.payments.filter(state=OrderPayment.PAYMENT_STATE_CONFIRMED).exists():
            return

        payment = self.order.payments.create(
            state=OrderPayment.PAYMENT_STATE_CREATED,
            provider='free',
            amount=Decimal('0.00'),
            fee=None,
        )
        try:
            payment.confirm(send_mail=False, count_waitinglist=False)
        except Quota.QuotaExceededException:
            messages.warning(
                self.request,
                _('The tickets have been canceled, but the order could not be marked as paid automatically.')
            )
