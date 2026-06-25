"""
ATS connector family — export NeuroSync results back into Applicant Tracking
Systems and synchronize candidate records.

ATS is just another connector family with an *export* direction (Volume 2B §7.4 /
Volume 4). Critically, NO ATS-specific logic lives inside the AI: the service
reads an already-computed session report and hands it to an ATS adapter that
formats and pushes it. Adapters translate the platform's normalized report into
each ATS's API and nothing else escapes the edge.
"""

from backend.ats import providers  # noqa: F401  (registers built-in ATS adapters)
