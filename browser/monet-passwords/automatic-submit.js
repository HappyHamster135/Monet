/* SPDX-License-Identifier: GPL-3.0-or-later */
'use strict';

// Browser-memory metadata only. Secrets pass straight to the native consent host;
// they are never put in local/session storage by this path.
class MonetSubmissionGate {
    constructor(send, cryptoProvider = globalThis.crypto, now = Date.now) {
        this.send = send;
        this.crypto = cryptoProvider;
        this.now = now;
        this.salt = cryptoProvider.getRandomValues(new Uint8Array(32));
        this.recent = new Map();
        this.steps = new Map();
    }
    flowOrigin(tab, url) {
        try {
            if (!Number.isInteger(tab?.id) || tab.id < 0 || typeof url !== 'string' || url.length > 8192) return '';
            const page = new URL(url), source = new URL(tab.url);
            if (page.origin !== source.origin || page.username || page.password || source.username || source.password) return '';
            if (page.protocol !== 'https:' && !(page.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(page.hostname))) return '';
            return page.origin;
        } catch (_) { return ''; }
    }
    rememberUsername(tab, username, url) {
        const origin = this.flowOrigin(tab, url);
        if (!origin || typeof username !== 'string' || !username || username.length > 4096) return false;
        for (const [id, entry] of this.steps) {
            if (this.now() - entry.time >= 120000) this.steps.delete(id);
        }
        if (this.steps.size >= 128 && !this.steps.has(tab.id)) return false;
        this.steps.set(tab.id, {origin, username, time: this.now()});
        return true;
    }
    username(tab, url) {
        const origin = this.flowOrigin(tab, url), step = this.steps.get(tab?.id);
        if (!origin || !step || step.origin !== origin || this.now() - step.time >= 120000) {
            this.steps.delete(tab?.id);
            return '';
        }
        return step.username;
    }
    clearFlow(tabId) {
        if (tabId === undefined) this.steps.clear();
        else this.steps.delete(tabId);
    }
    async submit(tab, args) {
        const [submitted, username, password, url, previous = []] = args;
        if (submitted !== true || !Number.isInteger(tab?.id) || tab.id < 0
            || typeof username !== 'string' || username.length > 4096
            || typeof password !== 'string' || !password || password.length > 4096
            || typeof url !== 'string' || url.length > 8192) return false;
        let origin;
        try {
            const page = new URL(url), source = new URL(tab.url);
            if (page.origin !== source.origin || page.username || page.password
                || source.username || source.password
                || !['https:', 'http:'].includes(page.protocol)) return false;
            if (page.protocol === 'http:' && !['localhost', '127.0.0.1', '[::1]'].includes(page.hostname)) return false;
            origin = page.origin;
        } catch (_) { return false; }
        const bytes = new TextEncoder().encode(JSON.stringify([origin, username, password]));
        const material = new Uint8Array(this.salt.length + bytes.length);
        material.set(this.salt); material.set(bytes, this.salt.length);
        const digest = new Uint8Array(await this.crypto.subtle.digest('SHA-256', material));
        material.fill(0); bytes.fill(0);
        const fingerprint = Array.from(digest, b => b.toString(16).padStart(2, '0')).join('');
        const old = this.recent.get(tab.id);
        if (old?.pending || (old?.fingerprint === fingerprint && this.now() - old.time < 120000)) return false;
        for (const [id, entry] of this.recent) {
            if (!entry.pending && this.now() - entry.time >= 120000) this.recent.delete(id);
        }
        if (this.recent.size >= 128 && !this.recent.has(tab.id)) return false;
        if ([...this.recent.values()].filter(entry => entry.pending).length >= 4) return false;
        const entry = {fingerprint, pending: true, time: this.now()};
        this.recent.set(tab.id, entry);
        try {
            const matches = Array.isArray(previous) ? previous.filter(p => p.login === username && typeof p.uuid === 'string') : [];
            // Native storage also verifies the UUID belongs to this exact origin.
            const result = await this.send(tab, {username, password, url: origin, uuid: matches.length === 1 ? matches[0].uuid : null});
            // A locked/disconnected vault did not ask the user: permit a retry
            // after unlocking rather than suppressing it for two minutes.
            if (!result?.prompted && !result?.saved) this.recent.delete(tab.id);
            return Boolean(result?.prompted || result?.saved);
        } catch (error) {
            this.recent.delete(tab.id);
            throw error;
        } finally {
            entry.pending = false;
            entry.time = this.now();
        }
    }
}
if (typeof module !== 'undefined') module.exports = MonetSubmissionGate;
