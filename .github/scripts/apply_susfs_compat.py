#!/usr/bin/env python3
"""Apply the upstream SUSFS patch across pre-refactor and current GKI 6.12.

Ported from xmicro's PR #342 ("Fix kernels <6.12.9x: SuSFS patch from not
applying correctly"), verified here against android16-6.12-2025-06
(deprecated), -2025-09, -2026-03, -2026-06 and -2026-09: zero rejects on all.
"""


