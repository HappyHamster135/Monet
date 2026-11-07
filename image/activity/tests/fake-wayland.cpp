// SPDX-License-Identifier: GPL-3.0-or-later
#include "fake-wayland.h"
#include "dpms-server-protocol.h"
#include <QSocketNotifier>
#include <algorithm>
#include <wayland-server-protocol.h>

FakeWayland::FakeWayland(QObject *parent) : QObject(parent), m_display(wl_display_create())
{
    if (!m_display || wl_display_add_socket(m_display, "monet-activity-test") != 0) qFatal("Cannot create private Wayland fixture");
    auto loop = wl_display_get_event_loop(m_display);
    m_notifier = std::make_unique<QSocketNotifier>(wl_event_loop_get_fd(loop), QSocketNotifier::Read);
    connect(m_notifier.get(), &QSocketNotifier::activated, this, [this, loop] {
        wl_event_loop_dispatch(loop, 0); wl_display_flush_clients(m_display);
    });
    addOutput(QStringLiteral("eDP-1")); addOutput(QStringLiteral("HDMI-A-1")); addManager();
}
FakeWayland::~FakeWayland()
{
    m_notifier.reset();
    wl_display_destroy_clients(m_display);
    wl_display_destroy(m_display);
    qDeleteAll(m_outputs);
}
void FakeWayland::addOutput(const QString &name, uint32_t mode)
{
    if (m_outputs.contains(name)) {
        auto output = m_outputs.value(name);
        if (!output->global) {
            output->mode = mode;
            output->global = wl_global_create(m_display, &wl_output_interface, 4, output, bindOutput);
            wl_display_flush_clients(m_display);
        }
        return;
    }
    auto output = new Output{this, name, mode, true, nullptr, {}, {}};
    output->global = wl_global_create(m_display, &wl_output_interface, 4, output, bindOutput);
    m_outputs.insert(name, output); wl_display_flush_clients(m_display);
}
void FakeWayland::removeOutput(const QString &name)
{
    auto output = m_outputs.value(name);
    if (!output || !output->global) return;
    wl_global_destroy(output->global); output->global = nullptr;
    // Retain the output's resource data until the client releases it.
    wl_display_flush_clients(m_display);
}
void FakeWayland::setMode(const QString &name, uint32_t mode) { m_outputs.value(name)->mode = mode; send(m_outputs.value(name)); }
void FakeWayland::setSupported(const QString &name, bool supported) { m_outputs.value(name)->supported = supported; send(m_outputs.value(name)); }
void FakeWayland::addManager()
{
    if (!m_manager) m_manager = wl_global_create(m_display, &org_kde_kwin_dpms_manager_interface, 1, this, bindManager);
    wl_display_flush_clients(m_display);
}
void FakeWayland::removeManager()
{
    wl_global_destroy(m_manager); m_manager = nullptr; wl_display_flush_clients(m_display);
}
void FakeWayland::release(wl_client *, wl_resource *resource) { wl_resource_destroy(resource); }
void FakeWayland::outputDestroyed(wl_resource *resource) {
    static_cast<Output *>(wl_resource_get_user_data(resource))->outputs.removeAll(resource);
}
void FakeWayland::dpmsDestroyed(wl_resource *resource) {
    static_cast<Output *>(wl_resource_get_user_data(resource))->dpms.removeAll(resource);
}
void FakeWayland::bindOutput(wl_client *client, void *data, uint32_t version, uint32_t id)
{
    auto output = static_cast<Output *>(data);
    auto resource = wl_resource_create(client, &wl_output_interface, std::min(version, uint32_t(4)), id);
    static const struct wl_output_interface implementation{release};
    wl_resource_set_implementation(resource, &implementation, output, outputDestroyed);
    output->outputs.append(resource);
    wl_output_send_geometry(resource, 0, 0, 300, 200, WL_OUTPUT_SUBPIXEL_UNKNOWN, "Monet fixture", "Virtual monitor", WL_OUTPUT_TRANSFORM_NORMAL);
    wl_output_send_mode(resource, WL_OUTPUT_MODE_CURRENT | WL_OUTPUT_MODE_PREFERRED, 1920, 1080, 60000);
    if (version >= 2) { wl_output_send_scale(resource, 1); wl_output_send_done(resource); }
    if (version >= 4) {
        wl_output_send_name(resource, output->name.toUtf8().constData());
        wl_output_send_description(resource, "Disposable test output");
        wl_output_send_done(resource);
    }
}
void FakeWayland::bindManager(wl_client *client, void *data, uint32_t, uint32_t id)
{
    auto resource = wl_resource_create(client, &org_kde_kwin_dpms_manager_interface, 1, id);
    static const struct org_kde_kwin_dpms_manager_interface implementation{getDpms};
    wl_resource_set_implementation(resource, &implementation, data, nullptr);
}
void FakeWayland::getDpms(wl_client *client, wl_resource *, uint32_t id, wl_resource *outputResource)
{
    auto output = static_cast<Output *>(wl_resource_get_user_data(outputResource));
    auto resource = wl_resource_create(client, &org_kde_kwin_dpms_interface, 1, id);
    static const struct org_kde_kwin_dpms_interface implementation{requestMode, release};
    wl_resource_set_implementation(resource, &implementation, output, dpmsDestroyed);
    output->dpms.append(resource);
    output->server->send(output);
}
void FakeWayland::requestMode(wl_client *, wl_resource *resource, uint32_t) {
    ++static_cast<Output *>(wl_resource_get_user_data(resource))->server->modeRequests;
}
void FakeWayland::send(Output *output)
{
    for (auto resource : std::as_const(output->dpms)) {
        org_kde_kwin_dpms_send_supported(resource, output->supported ? 1 : 0);
        org_kde_kwin_dpms_send_mode(resource, output->mode);
        org_kde_kwin_dpms_send_done(resource);
    }
    wl_display_flush_clients(m_display);
}
