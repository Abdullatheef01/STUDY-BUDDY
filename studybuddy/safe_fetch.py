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
import ipaddress
import logging
import socket
from urllib.parse import urlparse, urljoin

import requests

log = logging.getLogger(__name__)

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
        raise SSRFError("URL has no hostname")
    # IP literal? (urlparse().hostname strips brackets from IPv6 literals)
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        ip = None
    if ip is not None:
        if not ip.is_global:
            raise SSRFError(f"IP address {hostname} is not publicly routable")
        return [str(ip)]
    try:
        infos = socket.getaddrinfo(hostname, None, family=socket.AF_UNSPEC,
                                   type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise SSRFError(f"DNS resolution failed for {hostname!r}: {e}")
    except UnicodeError as e:
        raise SSRFError(f"Bad hostname {hostname!r}: {e}")
    ips = []
    for _fam, _typ, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            raise SSRFError(f"Unparseable resolved address {ip_str!r}")
        if not ip.is_global:
            raise SSRFError(
                f"Hostname {hostname!r} resolves to non-public IP {ip_str}")
        ips.append(ip_str)
    if not ips:
        raise SSRFError(f"Hostname {hostname!r} resolved to no addresses")
    return list(dict.fromkeys(ips))  # de-dupe, keep order


def validate_url(url):
    """Validate a user-supplied URL for server-side fetching.

    Returns the parsed URL (urllib.parse.ParseResult). Raises SSRFError
    with a human-readable reason on any problem.
    """
    if not url or not isinstance(url, str):
        raise SSRFError("Empty URL")
    url = url.strip()
    if len(url) > _MAX_URL_LEN:
        raise SSRFError("URL too long")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SSRFError(
            f"Scheme {parsed.scheme!r} not allowed (http/https only)")
    # urlparse puts userinfo in .username/.password; also catch a raw "@"
    # in case of tricky encodings the parser accepts.
    if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
        raise SSRFError("Credentials in URL are not allowed")
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
                    raise SSRFError("Redirect without Location header")
                hops += 1
                if hops > max_redirects:
                    raise SSRFError(
                        f"Too many redirects (>{max_redirects})")
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
                raise SSRFError(
                    f"Response exceeds {max_bytes}-byte cap")
        return resp.status_code, bytes(body), dict(resp.headers)
