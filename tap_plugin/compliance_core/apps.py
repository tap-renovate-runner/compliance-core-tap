"""TAP Compliance Core plugin AppConfig."""

from tap_plugins.base import TapPluginConfig


class ComplianceCoreConfig(TapPluginConfig):
    def ready(self) -> None:
        super().ready()  # MUST run first: it loads tap-plugin.toml

        # The report panel type (req-compliance-core-panel-report). Imported and registered in ready(), after every app has loaded.
        from tap_plugin.compliance_core.panels.report import ReportPanelType

        from tap_web.registry import panel_type_registry

        panel_type_registry.register(ReportPanelType.slug, ReportPanelType)
