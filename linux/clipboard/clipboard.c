/* SPDX-License-Identifier: GPL-3.0-or-later
 * Typed Wayland event boundary for the single-seat clipboard utilities. The
 * Python event loop owns the pipe fds. No surfaces or input grabs are used.
 */
#include "control.h"
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>

#define LIMIT 8192
#define EXPIRED "application/x-monet-expired"
struct offer {
    char *mime;
    int mixed, expired;
};
struct source {
    size_t len;
    char bytes[];
};
static struct wl_display *display;
static struct wl_seat *seat;
static struct ext_data_control_manager_v1 *manager;
static struct ext_data_control_device_v1 *device;
static uint32_t seat_id, manager_id;
static int failed, ready, owners;
static void (*receive_copy)(int);
static void (*observe)(int);
static void (*send_copy)(int, const char *, size_t);
static struct wl_callback *barrier;
static struct source *pending;

static void format(void *data, struct ext_data_control_offer_v1 *proxy, const char *mime)
{
    struct offer *offer = data;
    if (!offer) return;
    if (observe) {
        if (!strcmp(mime, EXPIRED)) offer->expired = 1;
        else offer->mixed = 1;
        return;
    }
    if (!strcasecmp(mime, "text/plain;charset=utf-8") ||
        !strcasecmp(mime, "text/plain; charset=utf-8") ||
        !strcasecmp(mime, "text/plain") || !strcmp(mime, "UTF8_STRING")) {
        // Request the advertised spelling. It belongs to the event until we return.
        if (!offer->mime || !strcasecmp(mime, "text/plain;charset=utf-8")) {
            free(offer->mime);
            offer->mime = strdup(mime);
        }
    } else if (strcmp(mime, "STRING") && strcmp(mime, "TEXT")) {
        offer->mixed = 1;
    }
}
static const struct ext_data_control_offer_v1_listener formats = {.offer = format};
static void new_offer(void *unused, struct ext_data_control_device_v1 *dev, struct ext_data_control_offer_v1 *proxy)
{
    ext_data_control_offer_v1_add_listener(proxy, &formats, calloc(1, sizeof(struct offer)));
}
static void discard(void *unused, struct ext_data_control_device_v1 *dev, struct ext_data_control_offer_v1 *proxy)
{
    if (!proxy) return;
    struct offer *offer = ext_data_control_offer_v1_get_user_data(proxy);
    if (offer) free(offer->mime);
    free(offer);
    ext_data_control_offer_v1_destroy(proxy);
}
static void selection(void *unused, struct ext_data_control_device_v1 *dev, struct ext_data_control_offer_v1 *proxy)
{
    int read_fd = -1, fds[2];
    if (barrier) {
        wl_callback_destroy(barrier);
        barrier = NULL;
    }
    free(pending);
    pending = NULL;
    struct offer *offer = proxy ? ext_data_control_offer_v1_get_user_data(proxy) : NULL;
    if (observe) {
        observe(proxy && !(offer && offer->expired && !offer->mixed));
        discard(NULL, dev, proxy);
        return;
    }
    if (ready && offer && !offer->mixed && offer->mime && pipe2(fds, O_CLOEXEC) == 0) {
        ext_data_control_offer_v1_receive(proxy, offer->mime, fds[1]);
        close(fds[1]);
        read_fd = fds[0];
    }
    discard(NULL, dev, proxy);
    receive_copy(read_fd);
}
static void finished(void *unused, struct ext_data_control_device_v1 *dev) { failed = 1; }
static const struct ext_data_control_device_v1_listener selections = {
    .data_offer = new_offer, .selection = selection, .finished = finished, .primary_selection = discard
};
static void global(void *unused, struct wl_registry *registry, uint32_t id, const char *name, uint32_t version)
{
    if (!seat && !strcmp(name, "wl_seat")) {
        seat = wl_registry_bind(registry, id, &wl_seat_interface, 1);
        seat_id = id;
    } else if (!manager && !strcmp(name, "ext_data_control_manager_v1")) {
        manager = wl_registry_bind(registry, id, &ext_data_control_manager_v1_interface, 1);
        manager_id = id;
    }
}
static void removed(void *unused, struct wl_registry *registry, uint32_t id)
{
    if (id == seat_id || id == manager_id) failed = 1;
}
static const struct wl_registry_listener globals = {.global = global, .global_remove = removed};

static void send_data(void *data, struct ext_data_control_source_v1 *proxy, const char *mime, int fd)
{
    struct source *source = data;
    if (!source || !strcmp(mime, "application/x-monet-clean-link")) close(fd);
    else send_copy(fd, source->bytes, source->len);
}
static void cancelled(void *data, struct ext_data_control_source_v1 *proxy)
{
    ext_data_control_source_v1_destroy(proxy);
    free(data);
    owners--;
}
static const struct ext_data_control_source_v1_listener transfers = {.send = send_data, .cancelled = cancelled};

static void publish(void *unused, struct wl_callback *callback, uint32_t serial)
{
    wl_callback_destroy(callback);
    barrier = NULL;
    // Any intervening selection event discarded pending, including clear.
    if (!observe && !pending) return;
    struct ext_data_control_source_v1 *source = ext_data_control_manager_v1_create_data_source(manager);
    if (!source) { failed = 1; return; }
    ext_data_control_source_v1_add_listener(source, &transfers, pending);
    pending = NULL;
    owners++;
    if (observe) {
        // Klipper restores history after a NULL selection. An empty marker has
        // no pasteable formats and leaves the independent primary selection alone.
        ext_data_control_source_v1_offer(source, EXPIRED);
        ext_data_control_device_v1_set_selection(device, source);
        return;
    }
    ext_data_control_source_v1_offer(source, "text/plain;charset=utf-8");
    ext_data_control_source_v1_offer(source, "text/plain");
    ext_data_control_source_v1_offer(source, "UTF8_STRING");
    ext_data_control_source_v1_offer(source, "application/x-monet-clean-link");
    ext_data_control_device_v1_set_selection(device, source);
}
static const struct wl_callback_listener synced = {.done = publish};

static int open_display(void)
{
    display = wl_display_connect(NULL);
    if (!display) return -1;
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &globals, NULL);
    if (wl_display_roundtrip(display) < 0 || !manager || !seat || failed) return -1;
    device = ext_data_control_manager_v1_get_data_device(manager, seat);
    ext_data_control_device_v1_add_listener(device, &selections, NULL);
    // An existing clipboard belongs to the user who copied it before enabling.
    if (wl_display_roundtrip(display) < 0 || failed) return -1;
    ready = 1;
    return wl_display_get_fd(display);
}
int clip_open(void (*receive)(int), void (*send)(int, const char *, size_t))
{
    receive_copy = receive;
    send_copy = send;
    return open_display();
}
int clip_open_observer(void (*changed)(int))
{
    observe = changed;
    return open_display();
}
int clip_dispatch(void) { return wl_display_dispatch(display) < 0 || failed ? -1 : 0; }
int clip_flush(void)
{
    if (wl_display_flush(display) >= 0) return 0;
    return errno == EAGAIN ? 1 : -1;
}
static void sync_selection(void)
{
    if (!barrier) {
        barrier = wl_display_sync(display);
        wl_callback_add_listener(barrier, &synced, NULL);
    }
}
// Wait for queued copies before expiring, and for KWin to acknowledge the
// resulting selection before releasing the logind sleep-delay inhibitor.
int clip_expire(void)
{
    sync_selection();
    if (wl_display_roundtrip(display) < 0 || failed) return -1;
    return wl_display_roundtrip(display) < 0 || failed ? -1 : 0;
}
void clip_replace(const char *text, size_t len)
{
    if (!len || len > LIMIT) return;
    free(pending);
    pending = malloc(sizeof(struct source) + len);
    if (!pending) return;
    pending->len = len;
    memcpy(pending->bytes, text, len);
    sync_selection();
}

int clip_retaining(void) { return owners; }
void clip_watch(int on)
{
    ready = on;
    free(pending);
    pending = NULL;
}
