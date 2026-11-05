'use strict';

// The connection belongs to the Electron main process, so the broker derives
// the real app/Flatpak identity from D-Bus credentials. No subprocess or socket
// carrying a claimed PID, and no auto-start of a disabled password service.
const NAME = 'org.monet.PasswordOffers1';
function createClient(dbus = require('dbus-next')) {
  async function call(member, body, signal) {
    let bus, timer, abort;
    try {
      if (signal?.aborted) return {status: 'cancelled'};
      bus = dbus.sessionBus();
      const fail = new Promise((_, reject) => {
        abort = () => reject(new Error('cancelled'));
        signal?.addEventListener('abort', abort, {once: true});
        bus.on('error', () => reject(new Error('unavailable')));
        timer = setTimeout(() => reject(new Error('timeout')), 105000);
      });
      const response = await Promise.race([fail, bus.call(new dbus.Message({
        destination: NAME, path: '/org/monet/PasswordOffers1', interface: NAME,
        member, signature: 's'.repeat(body.length), body,
        flags: dbus.MessageFlag.NO_AUTO_START
      }))]);
      const result = response.body[0];
      if (member === 'OfferDocumentLogin') return {status: String(result)};
      if (!result || typeof result.status !== 'string') return {status: 'unavailable'};
      if (result.status !== 'filled') return {status: result.status};
      if (typeof result.password !== 'string' || !result.password || result.password.length > 4096 ||
          typeof result.username !== 'string' || result.username.length > 320 || result.service !== body[2] ||
          (body[1] && result.username !== body[1])) return {status: 'unavailable'};
      return {status: 'filled', username: result.username, password: result.password, service: result.service};
    } catch { return {status: signal?.aborted ? 'cancelled' : 'unavailable'}; }
    finally { clearTimeout(timer); if (abort) signal?.removeEventListener('abort', abort); if (bus) bus.disconnect(); }
  }
  return {
    request: (document, username, service, signal) => call('RequestDocumentLogin', [document, username, service], signal),
    offer: (document, username, password, service, kind) => call('OfferDocumentLogin', [document, username, password, service, kind])
  };
}
module.exports = {createClient};
