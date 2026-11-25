"""Local rules for cleaning web addresses without re-encoding the retained fields."""
import ipaddress
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from urllib.parse import unquote_plus, urlsplit


DEFAULTS = {
    "": {"utm_*", "fbclid", "gclid", "dclid", "msclkid", "mc_eid", "mc_cid", "gbraid",
         "wbraid", "yclid", "twclid", "ttclid", "li_fat_id", "mkt_tok", "_hsenc", "_hsmi",
         "igshid", "__twitter_impression", "fb_action_ids", "fb_action_types", "mibextid"},
    "youtube.com": {"si", "feature"}, "youtu.be": {"si", "feature"},
    "spotify.com": {"si"}, "instagram.com": {"igsh"},
    "twitter.com": {"s", "t", "ref_src", "ref_url"}, "x.com": {"s", "t", "ref_src", "ref_url"},
    "reddit.com": {"share_id", "rdt", "ref_campaign", "ref_source", "correlation_id",
                   "_branch_match_id", "$deep_link", "$3p", "$original_url"},
    "tiktok.com": {"_t", "_r", "share_app_name", "share_iid"},
    "bilibili.com": {"vd_source", "spm_id_from", "share_source", "share_session_id"},
    "xiaohongshu.com": {"xhsshare", "share_from_user_hidden", "share_id"},
}
SIGNED = {"sig", "signature", "policy", "key-pair-id", "token", "access_token",
          "auth", "hmac", "jwt", "expires", "oauth_signature"}
RULE_FILE = "link-rules.json"


class RulesError(ValueError):
    """An unreadable rule file must never be overwritten with defaults."""


def site_name(text):
    host = text.strip().removesuffix(".").lower()
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        host = ""
    if len(host) > 253 or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
                                  for part in host.split(".")):
        raise ValueError("Enter a website name such as example.com.")
    return host


def rule_name(text):
    name = text.strip().casefold()
    if name != "utm_*" and not re.fullmatch(r"[\w.$~-]{1,128}", name):
        raise ValueError("Enter a parameter name such as ref or utm_source.")
    return name


def rules_path():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "monet" / RULE_FILE


def read_rules():
    try:
        value = json.loads(rules_path().read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError
        for site, group in value.items():
            if (site and site_name(site) != site) or not isinstance(group, dict):
                raise ValueError
            if any(rule_name(k) != k or type(v) is not bool for k, v in group.items()):
                raise ValueError
        return value
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        raise RulesError("Couldn’t read the saved link rules.") from error


def effective_rules(site, edits):
    """Apply broad rules first so that an exception for a subdomain wins."""
    scopes = [""]
    if site:
        try:
            ipaddress.ip_address(site)
            scopes.append(site)
        except ValueError:
            parts = site.split(".")
            scopes.extend(".".join(parts[i:]) for i in reversed(range(len(parts))))
    result = {}
    for scope in scopes:
        result.update(dict.fromkeys(DEFAULTS.get(scope, ()), True))
        result.update(edits.get(scope, {}))
    return result


def set_rule(site, name, enabled):
    import fcntl
    site = site_name(site) if site else ""
    name = rule_name(name)
    path = rules_path()
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        edits = read_rules()
        group = edits.setdefault(site, {})
        group.pop(name, None)
        if enabled is not None and enabled != effective_rules(site, edits).get(name):
            group[name] = enabled
        if not group:
            del edits[site]
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
            try:
                json.dump(edits, tmp, sort_keys=True)
                tmp.flush()
                os.replace(tmp.name, path)
            finally:
                Path(tmp.name).unlink(missing_ok=True)
    return edits


def clean_link(text, rules=None):
    """Return the cleaned address and unique removed names, preserving URL spelling."""
    value = text.strip()
    if not value or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value) or "\\" in value:
        raise ValueError("Copy one web link first.")
    parts = urlsplit(value)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError("Copy one web link first.")
    before_fragment, hash_mark, fragment = value.partition("#")
    base, question, query = before_fragment.partition("?")
    if not question or parts.username is not None:
        return value, []
    fields = [(unquote_plus(p.partition("=")[0]).casefold(), p) for p in query.split("&")]
    if any(k in SIGNED or k.startswith(("x-amz-", "x-goog-")) for k, _ in fields):
        return value, []
    try:
        site = site_name(parts.hostname)
    except ValueError:
        site = ""
    active = effective_rules(site, read_rules() if rules is None else rules)
    removed, keep = {}, []
    for key, raw in fields:
        if active.get(key, key.startswith("utm_") and active.get("utm_*", False)):
            removed[key] = None
        else:
            keep.append(raw)
    if not removed:
        return value, []
    return base + ("?" + "&".join(keep) if keep else "") + hash_mark + fragment, list(removed)


def clean_url(text):
    return clean_link(text)[0]
