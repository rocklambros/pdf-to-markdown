# Security Policy

## Supported versions

| Version | Status |
|---|---|
| 1.0.x   | ✅ Supported (current stable). Patch releases for security and quality fixes are published as needed. |
| 0.7.x   | ⚠️ Receives critical security fixes only until 2026-10-26 (six months after the v1.0.0 GA on 2026-04-26). |
| < 0.7   | ❌ Not supported. Please upgrade. |

## Reporting a vulnerability

**Please do not file public issues for security vulnerabilities.** Public
disclosure before a fix is published puts users at risk.

Email security disclosures to **rock@rockcyber.com** with the subject line
`any2md security disclosure`. Encrypted email is welcome — request a
public key in your initial message and one will be provided.

Include in your report:

- A description of the issue and the affected component.
- Affected version(s) — e.g., `pip show any2md` output, or commit SHA.
- Reproduction steps (smallest possible repro is ideal).
- Any proof-of-concept (please redact sensitive data).
- Whether you intend to publish your own write-up; if so, a proposed
  embargo date so we can coordinate.

### Response timeline

- **Acknowledgement** within 5 business days.
- **Triage and severity assessment** within 10 business days.
- **Critical issues** (remote code execution, data exfiltration via
  crafted input, supply-chain compromise of a published wheel): patched
  and released within 30 days of confirmation, with a coordinated public
  advisory.
- **High** (denial-of-service, information disclosure with limited blast
  radius): patched within 60 days.
- **Medium / low** issues are tracked in private until a fix lands in a
  scheduled release, then disclosed publicly via the GitHub Security
  Advisories page.

## Scope

In scope:

- The `any2md` library and CLI.
- The published wheels and sdists on PyPI.
- The release pipeline (`.github/workflows/publish.yml`) and any
  side-effects of running the workflow.
- The default conversion pipeline (PDF / DOCX / HTML / URL / TXT) and
  the optional Docling backend integration.
- The arxiv API enrichment path (network call + XML parsing).
- The SSRF guards in the URL fetcher.

Out of scope:

- Vulnerabilities in third-party dependencies (please file directly with
  the upstream — Docling, PyMuPDF, mammoth, trafilatura, BeautifulSoup,
  lxml, etc.). We monitor upstream advisories via Dependabot.
- Issues that require local filesystem access already granted to the
  running Python process.
- Local timing attacks against your own machine.
- Content correctness issues in converted Markdown (those are
  conversion-quality reports — please use the
  [Conversion quality issue template](.github/ISSUE_TEMPLATE/conversion_quality.md)
  instead).

## Hardening reference

If you operate any2md in a hardened environment:

- Pass `--no-arxiv-lookup` to disable the arxiv API call.
- Pass `--max-file-size` with a budget appropriate for your workload.
- Run conversions in a sandbox that cannot reach private networks
  (the SSRF guard validates resolved IPs, but defense in depth is best).
- Pin `any2md` and its extras (`any2md[high-fidelity]==<exact-version>`)
  to a verified version and audit the lockfile.

## Disclosure history

No publicly disclosed vulnerabilities to date. Future advisories will
appear at https://github.com/rocklambros/any2md/security/advisories.
