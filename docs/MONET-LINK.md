# Monet Link

Monet Link appears in **Settings → Phone** once this account has a relay
configuration. Select **Pair a phone**, open **Together → Monet Link** on the
phone, and scan the PC's QR. Enter the six digits from the phone before the
invitation expires. You can then send notes in both directions. The PC saves
notes locally even while a relay request is in progress and shows **Received**
after verifying the phone's receipt. A user service handles retries while
Settings is closed.

With a current relay and phone app, **Choose a file to send…** queues a file
up to 64 MiB. The encrypted local copy stays queued through a disconnect or
desktop service restart. Select **Save…** beside a completed file and choose
a folder. Link adds a numbered suffix if a file with that name already exists.
**Remove…** clears the Link copy and leaves any files saved outside Link.

A new phone handoff can show a generic desktop notification. **Open Phone
settings** opens the list of received handoffs. The notification contains no
handoff text, filenames or addresses. Retrying a receipt keeps the same local
entry.

During this development phase, the phone needs the Monet Link debug APK from
the Monet Phone repository. The PC needs access to a Monet Link development
relay. The existing local KDE Connect controls remain under the Link panel.

## Configure a development relay

Use the relay from [Monet Phone](https://github.com/HappyHamster135/Monet-Phone).
Give the relay an HTTPS address that both devices can reach and generate a
32-byte URL-safe provisioning key. Pass a private file containing that key to
`relay.py serve --provisioning-key-file`. The relay operator can revoke pairs
and rotate the provisioning key. The key grants permission to create new pairs,
so keep it in the operator's and PC account's private configuration.

Create `$XDG_CONFIG_HOME/monet/link/relay.json` (`~/.config/monet/link/relay.json`
by default) with permissions `0600`:

```json
{
  "url": "https://relay.example.net",
  "provisioningKey": "<relay provisioning key>"
}
```

For a test relay with a private certificate, add `"certificate": "relay.pem"`
and place the relay's public PEM file beside the configuration. The URL's host
must match the certificate. The Monet system image includes the required
`python3-cryptography`, `python3-qrcode+pil` and `libnotify` packages. On a
development overlay, install those packages separately and sign in again after installing
the units, or run `systemctl --user daemon-reload` and
`systemctl --user start monet-link.path`.

## Remove a phone

Use **Forget phone** in Settings. The PC clears the encrypted file copies in
Link. If the relay is offline, it pauses handoffs and retries revocation when
the relay returns. Once revocation succeeds, the PC clears the pairing and
the remaining Link history. On the phone, choose
**Forget computer** to clear local history and revoke the pairing after it
can reach the relay.

Link currently supports one phone per desktop account. It stores pairing keys
and received notes in an owner-only PC state file. Choose **Read** in
Settings to review a note or open a web link.
