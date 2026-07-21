"""Single source of the SARO platform version (STORY-375).

Everything that reports a version imports ``__version__`` from here — the FastAPI
app, the ``/health`` probe, the ``/api/v1/version`` endpoint, and the UI footer
(via that endpoint). A version string duplicated across files drifts, and a
drifted version on a status page or an evidence export is worse than none: it
tells a customer's change-management process something false.

SemVer (https://semver.org). Bump here, add a CHANGELOG entry, tag ``v<x.y.z>``.
"""

__version__ = "8.0.0"
