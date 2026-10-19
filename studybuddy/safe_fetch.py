"""SSRF-safe HTTP fetcher (SEC-02, Phase 0).

Every server-side fetch of a user-supplied URL MUST go through this module.
It defends against Server-Side Request Forgery:

* scheme allowlist (http/https only) — no file://, ftp://, gopher://, …
* no credentials in URL (user:pass@host)
* hostname must resolve via DNS and EVERY resolved A/AAAA address must be
  publicly routable (``ip.is_global``) — blocks 127.0.0.1, 10/8, 172.16/12,
  192.168/16, 169.254.169.254 (cloud metadata), ::1, fc00::/7, 0.0.0.0, …
* redirects are followed manually (max 3) with each hop re-validated —
  a safe first hop cannot bounce to a private address
* response bodies are capped (default 5 MiB)

Residual risk (documented): DNS is validated at request time; a hostile DNS
that flips an answer between validation and connect (rebinding) is not
defended here. The primary SSRF vectors — private IPs, metadata endpoints,
non-HTTP schemes — are closed.
"""
from __future__ import annotations

import contextlib
import hashlib
import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlparse

import requests

log = logging.getLogger(__name__)


def _deny(category, message, host=None):
    """SEC-14: log an SSRF policy block, then raise SSRFError.

    Only the block category and a hashed hostname are logged — never
    the full URL (it may carry query-string PII). Logging must never
    break the fetch path.
    """
    try:
        from studybuddy.security_events import log_security_event
        details = {"reason": category}
        if host:
            details["host_hash"] = hashlib.sha256(
                str(host).encode("utf-8")).hexdigest()[:16]
        log_security_event("ssrf_block", details=details)
    except Exception:
        pass
    raise SSRFError(message)

_USER_AGENT = "STUDY-BUDDY/1.0 (SSRF-safe fetcher)"
_MAX_REDIRECTS = 3
_DEFAULT_TIMEOUT = 10
_DEFAULT_MAX_BYTES = 5 * 1024 * 1024
_MAX_URL_LEN = 2048


class SSRFError(ValueError):
    """Raised when a URL is rejected by SSRF validation or the fetch fails."""


def _validated_ips(hostname):
    """Resolve hostname; return de-duplicated IP strings, all public.

    Raises SSRFError if the hostname is missing, unresolvable, an IP
    literal that is not public, or resolves to any non-public address.
    """
    if not hostname:
        _deny("missing_hostname", "URL has no hostname")
    # IP literal? (urlparse().hostname strips brackets from IPv6 literals)
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        ip = None
    if ip is not None:
        if not ip.is_global:
            _deny("private_ip_literal", f"IP address {hostname} is not publicly routable", host=hostname)
        return [str(ip)]
    try:
        infos = socket.getaddrinfo(hostname, None, family=socket.AF_UNSPEC,
                                   type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        _deny("dns_failure", f"DNS resolution failed for {hostname!r}: {e}", host=hostname)
    except UnicodeError as e:
        _deny("bad_hostname", f"Bad hostname {hostname!r}: {e}", host=hostname)
    ips = []
    for _fam, _typ, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            _deny("bad_resolved_ip", f"Unparseable resolved address {ip_str!r}", host=hostname)
        if not ip.is_global:
            _deny("private_resolved_ip",
              f"Hostname {hostname!r} resolves to non-public IP {ip_str}",
              host=hostname)
        ips.append(ip_str)
    if not ips:
        _deny("no_addresses", f"Hostname {hostname!r} resolved to no addresses", host=hostname)
    return list(dict.fromkeys(ips))  # de-dupe, keep order


def validate_url(url):
    """Validate a user-supplied URL for server-side fetching.

    Returns the parsed URL (urllib.parse.ParseResult). Raises SSRFError
    with a human-readable reason on any problem.
    """
    if not url or not isinstance(url, str):
        _deny("empty_url", "Empty URL")
    url = url.strip()
    if len(url) > _MAX_URL_LEN:
        _deny("url_too_long", "URL too long")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        _deny("bad_scheme",
              f"Scheme {parsed.scheme!r} not allowed (http/https only)")
    # urlparse puts userinfo in .username/.password; also catch a raw "@"
    # in case of tricky encodings the parser accepts.
    if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
        _deny("url_credentials", "Credentials in URL are not allowed")
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL has no hostname")
    _validated_ips(hostname)
    return parsed


@contextlib.contextmanager
def safe_fetch_stream(url, method="GET", timeout=_DEFAULT_TIMEOUT,
                      headers=None, max_redirects=_MAX_REDIRECTS):
    """Yield a streaming requests.Response for a validated URL.

    Redirects (301/302/303/307/308) are followed manually, each hop
    re-validated, up to max_redirects. The caller MUST consume or close the
    response; it is closed automatically on context exit.
    Raises SSRFError on validation failure, fetch failure, or redirect abuse.
    """
    hdrs = {"User-Agent": _USER_AGENT}
    if headers:
        hdrs.update(headers)
    current = url
    hops = 0
    resp = None
    try:
        while True:
            validate_url(current)
            try:
                resp = requests.request(method, current, headers=hdrs,
                                        timeout=timeout, allow_redirects=False,
                                        stream=True)
            except requests.RequestException as e:
                raise SSRFError(
                    f"Fetch failed ({type(e).__name__}): {e}")
            code = resp.status_code
            if code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("Location")
                resp.close()
                resp = None
                if not loc:
                    _deny("bad_redirect", "Redirect without Location header", host=urlparse(current).hostname)
                hops += 1
                if hops > max_redirects:
                    _deny("too_many_redirects",
                      f"Too many redirects (>{max_redirects})",
                      host=urlparse(current).hostname)
                current = urljoin(current, loc)
                if code == 303 or (code in (301, 302) and method != "HEAD"):
                    # 303 always becomes GET; 301/302 downgrade non-HEAD.
                    method = "GET"
                continue
            yield resp
            return
    finally:
        if resp is not None:
            resp.close()


def safe_fetch(url, method="GET", timeout=_DEFAULT_TIMEOUT,
               max_bytes=_DEFAULT_MAX_BYTES, headers=None,
               max_redirects=_MAX_REDIRECTS):
    """Fetch a user-supplied URL, returning (status_code, body, headers).

    Body is capped at max_bytes (SSRFError if exceeded). Redirects are
    validated per hop. Raises SSRFError on any problem. Never leaks
    tracebacks — the message is safe to surface.
    """
    with safe_fetch_stream(url, method=method, timeout=timeout,
                           headers=headers,
                           max_redirects=max_redirects) as resp:
        body = bytearray()
        for chunk in resp.iter_content(chunk_size=65536):
            if not chunk:
                continue
            body.extend(chunk)
            if len(body) > max_bytes:
                _deny("body_too_large",
                  f"Response exceeds {max_bytes}-byte cap",
                  host=urlparse(url).hostname)
        return resp.status_code, bytes(body), dict(resp.headers)
