'use strict';

// Call only from a trusted main-process action. Never expose this object over
// contextBridge or accept arbitrary renderer-supplied WebContents/selectors.
const {randomBytes} = require('node:crypto');
const {createClient} = require('./bus.cjs');
const {inspect} = require('./form.cjs');
const active = new WeakSet();
const WORLD = 734196;

function scope(value) {
  if (typeof value !== 'string' || value.length > 4096 || /[\x00-\x20\x7f-\x9f\\]/.test(value)) throw Error('Invalid document');
  const u = new URL(value);
  if (u.username || u.password) throw Error('Invalid document');
  if (u.protocol === 'file:' && !u.host && u.pathname.startsWith('/')) return 'file://' + u.pathname;
  if (!u.hostname || !['https:', 'http:', 'app:', 'tauri:', 'capacitor:', 'ionic:'].includes(u.protocol)) throw Error('Invalid document');
  if (u.protocol === 'http:' && u.hostname !== 'localhost' && u.hostname !== '[::1]' && !/^127(?:\.\d{1,3}){3}$/.test(u.hostname)) throw Error('Invalid document');
  return u.protocol + '//' + u.host;
}

function createIntegration({allowedDocuments, client = createClient(), worldId = WORLD}) {
  if (!Array.isArray(allowedDocuments) || !allowedDocuments.length || allowedDocuments.length > 32 ||
      !Number.isInteger(worldId) || worldId <= 999) throw Error('Explicit trusted document scopes are required');
  const allowed = new Set(allowedDocuments.map(scope));
  function permitted(contents) {
    if (contents.isDestroyed() || contents.getType() !== 'window' || !allowed.has(scope(contents.getURL()))) return false;
    const prefs = contents.getLastWebPreferences();
    return prefs.contextIsolation === true && prefs.sandbox === true && prefs.nodeIntegration === false;
  }
  async function fill(contents, fields) {
    if (active.has(contents)) return {status: 'busy'};
    let token, url, changed = false;
    const controller = new AbortController();
    const invalidate = () => { changed = true; controller.abort(); };
    const execute = code => contents.executeJavaScriptInIsolatedWorld(worldId, [{code}]);
    try {
      if (!permitted(contents) || !fields || !['username', 'password'].every(k => typeof fields[k] === 'string' && fields[k].length <= 512) ||
          (fields.service !== undefined && (typeof fields.service !== 'string' || fields.service.length > 512))) return {status: 'unsupported'};
      active.add(contents); url = contents.getURL(); token = '__monet_' + randomBytes(24).toString('hex');
      for (const e of ['did-start-navigation', 'did-navigate-in-page', 'render-process-gone', 'destroyed']) contents.on(e, invalidate);
      const context = await execute('(' + inspect.toString() + ')(' + JSON.stringify(fields) + ',' + JSON.stringify(token) + ')');
      if (!context || context.hasPassword || changed || contents.getURL() !== url) return {status: 'unavailable'};
      const login = await client.request(url, context.username, context.service, controller.signal);
      if (login.status !== 'filled') return {status: login.status};
      if (changed || !permitted(contents) || contents.getURL() !== url || typeof login.password !== 'string' ||
          !login.password || login.password.length > 4096 || typeof login.username !== 'string' || login.username.length > 320 ||
          login.service !== context.service || (context.username && context.username !== login.username)) return {status: 'cancelled'};
      const filled = await execute('Boolean(globalThis[' + JSON.stringify(token) + ']?.apply(' + JSON.stringify(login) + '))');
      // Only status leaves the main-process helper; never return credentials to
      // page callers, log them, use the clipboard or submit the form.
      return {status: filled ? 'filled' : 'cancelled'};
    } catch { return {status: 'unavailable'}; }
    finally {
      if (token) {
        try { if (!contents.isDestroyed()) await execute('globalThis[' + JSON.stringify(token) + ']?.clear()'); } catch {}
        for (const e of ['did-start-navigation', 'did-navigate-in-page', 'render-process-gone', 'destroyed']) contents.removeListener(e, invalidate);
      }
      active.delete(contents);
    }
  }
  async function offer(contents, values) {
    try {
      if (!permitted(contents) || !values || typeof values.username !== 'string' || values.username.length > 320 ||
          typeof values.password !== 'string' || !values.password || values.password.length > 4096 ||
          typeof values.service !== 'string' || values.service.length > 200 || !['login', 'register', 'change'].includes(values.kind)) return {status: 'invalid'};
      const result = await client.offer(contents.getURL(), values.username, values.password, values.service, values.kind);
      return {status: result.status};
    } catch { return {status: 'unavailable'}; }
  }
  return {fill, offer};
}
module.exports = {createIntegration};
