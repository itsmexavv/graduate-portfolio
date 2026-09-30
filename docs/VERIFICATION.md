# Verification record

Verified on 2026-09-30 with Python 3.12.14 and Node 24.19.0. Browser verification used Playwright 1.51.1 with Chromium Headless Shell 134 in a temporary test environment. These describe the actual verification environment, not required production versions.

| Check | Result |
| --- | --- |
| Python business-rule and HTTP integration tests | 30 passed |
| JavaScript syntax check | Passed |
| SmartFind browser workflow | Search, add product, adjust stock passed |
| AttendFlow browser workflow | Check-in, check-out, add student, create event passed |
| PesoLens browser workflow | Add exact-value expense and render totals passed |
| AccessPath browser workflow | 220 m step-free route, 170 m stairs shortcut and unreachable closure passed |
| MiniLang browser workflow | Example output, AST display and division-by-zero handling passed |
| Mobile pages at 390 px width | Overview and all five project pages passed horizontal-overflow checks |
| Browser runtime | No unexpected JavaScript or console errors |
| Screenshots | Six desktop screenshots and one mobile overview captured and visually reviewed |

Business tests use fresh temporary databases. Browser tests use a separate disposable seeded database set. Neither test dataset is included in the downloadable source.

GitHub Actions is configured in `.github/workflows/tests.yml`; this record does not claim a remote workflow has already run. Python 3.11 and 3.13 are configured CI targets but were not locally executed in this environment.

Browser verification is workflow coverage, not an accessibility audit or cross-browser guarantee. No production load/security assessment was performed.
