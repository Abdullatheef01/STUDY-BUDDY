"""Shared harsh input corpus for mega tests.

Every string here is designed to break naive code: empty, whitespace-only,
oversized, unicode edge cases, injection payloads, control characters.
"""
import math

HARSH_STRINGS = [
    "", " ", "   ", "\n", "\t", "\r\n", "\x00", "\x00\x00",
    "a", "a" * 10, "a" * 1000, "a" * 100_000,
    "hello world", "HELLO WORLD", "Hello World",
    "café naïve résumé", "日本語テスト", "中文测试", "العربية",
    "emoji 😀🎉🚀💯", "😀" * 500,
    "line1\nline2\nline3", "tab\there", "carriage\rreturn",
    # XSS payloads
    "<script>alert(1)</script>", "<img src=x onerror=alert(1)>",
    "\"><script>alert('xss')</script>", "';alert(String.fromCharCode(88,83,83))//",
    "<svg/onload=alert(1)>", "javascript:alert(1)",
    # SQL injection payloads
    "' OR '1'='1", "'; DROP TABLE users; --", "' UNION SELECT * FROM users --",
    "1; DELETE FROM users WHERE 1=1",
    # Path traversal
    "../../etc/passwd", "..\\..\\windows\\system32", "/etc/passwd",
    "....//....//etc/passwd",
    # Format string / template injection
    "%s %s %s", "{0}{1}", "{{7*7}}", "${7*7}", "#{7*7}",
    # Special
    "None", "null", "undefined", "NaN", "Infinity", "-Infinity",
    "0", "-0", "0.0", ".5", "5.",
    "<!-- comment -->", "<![CDATA[data]]>",
    "a" * 10 + "\x00" + "b" * 10,
    "\u202e reversed \u202c text",  # bidi override
    "\ufeff BOM start",
    "word " * 10000,  # 50k chars of words
]

HARSH_NUMBERS = [
    0, 1, -1, 2, -2, 100, -100,
    2**31 - 1, 2**31, -(2**31), 2**63 - 1,
    1.5, -1.5, 0.1, 999999.99,
    float('inf'), float('-inf'),
]

HARSH_NUMBERS_SAFE = [n for n in HARSH_NUMBERS
                      if not (isinstance(n, float) and math.isinf(n))]

HARSH_IDS = ["0", "-1", "999999999", "abc", "", " ", "1.5", "0x10", "../1",
             "%2e%2e/1", "\x00", "１２３"]

HARSH_EMAILS = ["", "a", "@", "a@", "@b.com", "a@b", "a@b.c" * 100,
                "test@test.com", "TEST@TEST.COM", "a b@c.com",
                "<script>@x.com", "a@b.com\nCc: evil@x.com"]
