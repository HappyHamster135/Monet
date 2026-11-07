var candidates = panels().filter(function (panel) { return panel.widgets("org.monet.quick").length > 0; });
if (candidates.length) {
    var panel = candidates[candidates.length - 1];
    var widgets = panel.widgets("org.monet.transfers");
    var widget = widgets.length ? widgets[0] : panel.addWidget("org.monet.transfers");
    if (widget) {
        widget.currentConfigGroup = ["General"];
        widget.writeConfig("openRequest", String(Date.now()));
        widget.reloadConfig();
    }
}
