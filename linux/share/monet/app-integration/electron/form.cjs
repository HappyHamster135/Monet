'use strict';

// Serialized into a private isolated world, never the page's JavaScript world.
// A candidate keeps the actual nodes, form/action and full URL across consent.
function inspect(options, token) {
  const input = selector => {
    const nodes = document.querySelectorAll(selector);
    if (nodes.length !== 1 || !(nodes[0] instanceof HTMLInputElement)) throw Error('ambiguous');
    return nodes[0];
  };
  const visible = n => n.isConnected && !n.disabled && !n.closest('[inert]') &&
    n.getClientRects().length > 0 && getComputedStyle(n).visibility === 'visible';
  const user = input(options.username), password = input(options.password);
  const form = password.form;
  if (!form || user.form !== form || user === password || password.type !== 'password' ||
      !['text', 'email', 'tel'].includes(user.type) || password.readOnly ||
      !visible(user) || !visible(password) || password.autocomplete !== 'current-password' || (user.readOnly && !user.value) ||
      form.querySelectorAll('input[type="password"]').length !== 1) return null;
  const service = options.service ? input(options.service) : null;
  if (service && (service.form !== form || !visible(service) || service.type === 'password')) return null;
  const attributes = n => [n.type, n.id, n.name, n.autocomplete];
  const fields = [user, password, ...(service ? [service] : [])].map(n => [n, attributes(n)]);
  const capture = {deadline: Date.now() + 90000, url: location.href, action: form.action, method: form.method,
    username: user.value, password: password.value, service: service ? service.value : '',
    userReadonly: user.readOnly, autocomplete: password.autocomplete,
    buttons: [...form.querySelectorAll('button,input[type="submit"]')].map(n => [n, n.textContent, n.getAttribute('type'), n.getAttribute('formaction')])};
  const valid = () => Date.now() < capture.deadline && document.visibilityState === 'visible' && location.href === capture.url && document.contains(form) && user.form === form &&
    password.form === form && visible(user) && visible(password) && !password.readOnly &&
    fields.every(([n, before]) => attributes(n).every((value, i) => value === before[i])) && user.readOnly === capture.userReadonly &&
    password.autocomplete === capture.autocomplete && user.value === capture.username && password.value === capture.password &&
    form.action === capture.action && form.method === capture.method &&
    form.querySelectorAll('input[type="password"]').length === 1 &&
    (!service || (visible(service) && service.form === form && service.value === capture.service)) &&
    capture.buttons.length === form.querySelectorAll('button,input[type="submit"]').length &&
    capture.buttons.every(([n, label, type, action]) => n.isConnected && form.contains(n) &&
      n.textContent === label && n.getAttribute('type') === type && n.getAttribute('formaction') === action);
  const timer = setTimeout(() => { delete globalThis[token]; }, 100000);
  globalThis[token] = {
    clear() { clearTimeout(timer); delete globalThis[token]; },
    apply(login) {
      if (!valid() || capture.password || (capture.username && capture.username !== login.username) ||
          (user.readOnly && capture.username !== login.username) || capture.service !== login.service) return false;
      const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      // Both nodes are revalidated together. Set both before dispatching events,
      // so page input handlers cannot replace the password target mid-fill.
      if (!user.readOnly) set.call(user, login.username);
      set.call(password, login.password);
      for (const n of [user, password]) {
        n.dispatchEvent(new Event('input', {bubbles: true}));
        n.dispatchEvent(new Event('change', {bubbles: true}));
      }
      return true;
    },
    valid
  };
  return {username: capture.username, service: capture.service, hasPassword: !!capture.password};
}
module.exports = {inspect};
