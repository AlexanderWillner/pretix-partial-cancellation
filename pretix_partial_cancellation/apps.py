from django.utils.translation import gettext_lazy as _

try:
    from pretix.base.plugins import PluginConfig, PLUGIN_LEVEL_EVENT
except ImportError as exc:
    raise RuntimeError("Please use pretix 2025.7 or above to run this plugin!") from exc


class PartialCancellationApp(PluginConfig):
    name = 'pretix_partial_cancellation'
    label = 'partial_cancellation'
    verbose_name = _("Partial cancellation")

    class PretixPluginMeta:
        name = _("Partial cancellation")
        author = _("Alexander Willner")
        version = '0.1.0'
        category = 'FEATURE'
        description = _("Allows customers to partially cancel tickets in free orders from the order page.")
        compatibility = "pretix>=2025.7.0"
        level = PLUGIN_LEVEL_EVENT
        settings_links = [
            ((_("Settings"), _("Partial cancellation")), "plugins:partial_cancellation:settings", {}),
        ]

    def ready(self):
        from . import signals  # NOQA
