// Exercise button and v120 wheel events on the fixture's private KWin EIS connection.
#include <libei.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>

// Wait until the compositor has received this device's frame before the
// fixture moves a second device or checks a client's button sequence.
static int sync_frame(struct ei *ctx, struct pollfd *io)
{
    struct ei_ping *ping = ei_new_ping(ctx);
    ei_ping(ping);
    ei_ping_unref(ping);
    while (poll(io, 1, 3000) > 0) {
        ei_dispatch(ctx);
        struct ei_event *event;
        while ((event = ei_get_event(ctx))) {
            enum ei_event_type type = ei_event_get_type(event);
            ei_event_unref(event);
            if (type == EI_EVENT_PONG) return 1;
            if (type == EI_EVENT_DISCONNECT) return 0;
        }
    }
    return 0;
}

int main(int argc, char **argv)
{
    if (argc != 2 && argc != 3) return 1;
    struct ei *ctx = ei_new_sender(NULL);
    if (argc == 3) ei_configure_name(ctx, argv[2]);
    if (ei_setup_backend_fd(ctx, atoi(argv[1])) != 0) return 1;
    struct pollfd io = { .fd = ei_get_fd(ctx), .events = POLLIN };
    struct ei_device *wheel = NULL;
    while (!wheel && poll(&io, 1, 4000) > 0) {
        ei_dispatch(ctx);
        struct ei_event *event;
        while ((event = ei_get_event(ctx))) {
            struct ei_device *device;
            switch (ei_event_get_type(event)) {
            case EI_EVENT_SEAT_ADDED:
                ei_seat_bind_capabilities(ei_event_get_seat(event), EI_DEVICE_CAP_POINTER,
                                          EI_DEVICE_CAP_SCROLL, EI_DEVICE_CAP_BUTTON, NULL);
                break;
            case EI_EVENT_DEVICE_RESUMED:
                device = ei_event_get_device(event);
                if (!wheel && ei_device_has_capability(device, EI_DEVICE_CAP_SCROLL))
                    wheel = ei_device_ref(device);
                break;
            case EI_EVENT_DISCONNECT:
                return 1;
            default:
                break;
            }
            ei_event_unref(event);
        }
    }
    if (!wheel) return 1;
    ei_device_start_emulating(wheel, 1);
    puts("ready");
    fflush(stdout);
    char kind;
    int x, y;
    while (scanf(" %c %d %d", &kind, &x, &y) == 3) {
        if (kind == 'd') ei_device_scroll_discrete(wheel, x, y);
        else if (kind == 'b') ei_device_button_button(wheel, x, y != 0);
        else if (kind == 'p') ei_device_scroll_delta(wheel, x, y);
        else return 1;
        ei_device_frame(wheel, ei_now(ctx));
        ei_dispatch(ctx);
        if (kind == 'b' && !sync_frame(ctx, &io)) return 1;
        puts("sent");
        fflush(stdout);
    }
    ei_device_stop_emulating(wheel);
    ei_device_unref(wheel);
    ei_unref(ctx);
    return 0;
}
