/* One Wayland connection owned by the open Display page. No polling or round trips. */
#include "dpms.h"
#include <errno.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <wayland-client.h>

struct monitor {
    struct monitor *next;
    uint32_t id;
    struct wl_output *output;
    struct org_kde_kwin_dpms *power;
    char *name, *description;
    bool supported, pending_supported;
    int mode, pending_mode;
};

struct connection {
    struct wl_display *display;
    struct wl_registry *registry;
    uint32_t manager_id;
    struct org_kde_kwin_dpms_manager *manager;
    struct monitor *monitors;
};

static void geometry(void *data, struct wl_output *out, int32_t x, int32_t y,
                     int32_t w, int32_t h, int32_t sub, const char *make, const char *model, int32_t transform) {}
static void output_mode(void *data, struct wl_output *out, uint32_t flags, int32_t w, int32_t h, int32_t hz) {}
static void output_done(void *data, struct wl_output *out) {}
static void scale(void *data, struct wl_output *out, int32_t factor) {}

static void set_string(char **field, const char *value)
{
    char *copy = strdup(value);
    if (copy) {
        free(*field);
        *field = copy;
    }
}
static void name(void *data, struct wl_output *out, const char *value)
{
    set_string(&((struct monitor *)data)->name, value);
}
static void description(void *data, struct wl_output *out, const char *value)
{
    set_string(&((struct monitor *)data)->description, value);
}
static const struct wl_output_listener output_events = {
    .geometry = geometry, .mode = output_mode, .done = output_done, .scale = scale,
    .name = name, .description = description
};

static void supported(void *data, struct org_kde_kwin_dpms *power, uint32_t value)
{
    ((struct monitor *)data)->pending_supported = value != 0;
}
static void mode(void *data, struct org_kde_kwin_dpms *power, uint32_t value)
{
    ((struct monitor *)data)->pending_mode = value <= ORG_KDE_KWIN_DPMS_MODE_OFF ? (int)value : -1;
}
static void done(void *data, struct org_kde_kwin_dpms *power)
{
    struct monitor *m = data;
    m->supported = m->pending_supported;
    m->mode = m->pending_mode;
}
static const struct org_kde_kwin_dpms_listener power_events = {
    .supported = supported, .mode = mode, .done = done
};

static void observe(struct connection *c, struct monitor *m)
{
    if (c->manager && !m->power) {
        m->power = org_kde_kwin_dpms_manager_get(c->manager, m->output);
        if (m->power) org_kde_kwin_dpms_add_listener(m->power, &power_events, m);
    }
}

static void added(void *data, struct wl_registry *registry, uint32_t id, const char *interface, uint32_t version)
{
    struct connection *c = data;
    if (strcmp(interface, wl_output_interface.name) == 0 && version >= 4) {
        struct monitor *m = calloc(1, sizeof(*m));
        if (!m) return;
        m->id = id;
        m->mode = m->pending_mode = -1;
        m->output = wl_registry_bind(registry, id, &wl_output_interface, 4);
        if (!m->output) { free(m); return; }
        wl_output_add_listener(m->output, &output_events, m);
        m->next = c->monitors;
        c->monitors = m;
        observe(c, m);
    } else if (!c->manager && strcmp(interface, org_kde_kwin_dpms_manager_interface.name) == 0) {
        c->manager_id = id;
        c->manager = wl_registry_bind(registry, id, &org_kde_kwin_dpms_manager_interface, 1);
        for (struct monitor *m = c->monitors; m; m = m->next) observe(c, m);
    }
}

static void forget(struct monitor *m)
{
    if (m->power) org_kde_kwin_dpms_release(m->power);
    wl_output_release(m->output);
    free(m->name);
    free(m->description);
    free(m);
}

static void removed(void *data, struct wl_registry *registry, uint32_t id)
{
    struct connection *c = data;
    if (c->manager && c->manager_id == id) {
        for (struct monitor *m = c->monitors; m; m = m->next) {
            if (m->power) org_kde_kwin_dpms_release(m->power);
            m->power = NULL;
            m->supported = m->pending_supported = false;
            m->mode = m->pending_mode = -1;
        }
        org_kde_kwin_dpms_manager_destroy(c->manager);
        c->manager = NULL;
        return;
    }
    for (struct monitor **link = &c->monitors; *link; link = &(*link)->next) {
        struct monitor *m = *link;
        if (m->id == id) {
            *link = m->next;
            forget(m);
            return;
        }
    }
}
static const struct wl_registry_listener registry_events = {.global = added, .global_remove = removed};

struct connection *monet_power_open(void)
{
    struct connection *c = calloc(1, sizeof(*c));
    if (!c) return NULL;
    c->display = wl_display_connect(NULL);
    if (!c->display) { free(c); return NULL; }
    c->registry = wl_display_get_registry(c->display);
    if (!c->registry) { wl_display_disconnect(c->display); free(c); return NULL; }
    wl_registry_add_listener(c->registry, &registry_events, c);
    return c;
}

int monet_power_fd(struct connection *c) { return wl_display_get_fd(c->display); }
int monet_power_dispatch(struct connection *c) { return wl_display_dispatch(c->display); }
int monet_power_flush(struct connection *c)
{
    if (wl_display_flush(c->display) >= 0) return 1;
    return errno == EAGAIN ? 0 : -1;
}

typedef void (*visitor)(uint32_t id, const char *name, const char *description, int on);
void monet_power_outputs(struct connection *c, visitor visit)
{
    for (struct monitor *m = c->monitors; m; m = m->next) {
        if (m->name && m->mode >= 0 && m->supported)
            visit(m->id, m->name, m->description ? m->description : "", m->mode == ORG_KDE_KWIN_DPMS_MODE_ON);
    }
}

int monet_power_set(struct connection *c, uint32_t id, const char *name, int on)
{
    for (struct monitor *m = c->monitors; m; m = m->next) {
        if (m->id == id && m->power && m->supported && m->name && strcmp(m->name, name) == 0) {
            org_kde_kwin_dpms_set(m->power, on ? ORG_KDE_KWIN_DPMS_MODE_ON : ORG_KDE_KWIN_DPMS_MODE_OFF);
            return 1;
        }
    }
    return 0;
}

void monet_power_close(struct connection *c)
{
    while (c->monitors) {
        struct monitor *next = c->monitors->next;
        forget(c->monitors);
        c->monitors = next;
    }
    if (c->manager) org_kde_kwin_dpms_manager_destroy(c->manager);
    wl_registry_destroy(c->registry);
    wl_display_disconnect(c->display);
    free(c);
}
