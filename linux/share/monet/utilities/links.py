"""Remove tracking parameters without decoding the rest of a web address."""
from urllib.parse import unquote_plus, urlsplit


def clean_url(text):
    """Leave signature-bearing URLs and the exact encoding of retained parameters intact."""
    value = text.strip()
    if not value or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value) or "\\" in value:
        raise ValueError("Copy one web link first.")
    parts = urlsplit(value)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError("Copy one web link first.")
    # Reassemble from the original spelling. urlunsplit normalizes the scheme
    # and drops empty fragment delimiters, both of which matter to some apps.
    before_fragment, hash_mark, fragment = value.partition("#")
    base, question, query = before_fragment.partition("?")
    if not question or parts.username is not None:
        return value
    fields = [(unquote_plus(p.partition("=")[0]).casefold(), p) for p in query.split("&")]
    signed = {"sig", "signature", "policy", "key-pair-id", "token", "access_token",
              "auth", "hmac", "jwt", "expires", "oauth_signature"}
    if any(k in signed or k.startswith(("x-amz-", "x-goog-")) for k, _ in fields):
        return value
    tracking = {"fbclid", "gclid", "dclid", "msclkid", "mc_eid", "mc_cid"}
    keep = [raw for key, raw in fields if not key.startswith("utm_") and key not in tracking]
    if len(keep) == len(fields):
        return value
    return base + ("?" + "&".join(keep) if keep else "") + hash_mark + fragment
