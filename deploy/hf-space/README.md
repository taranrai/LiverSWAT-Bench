---
title: LiverSWAT-Bench judge runner
sdk: docker
app_port: 7860
pinned: false
---

# LiverSWAT-Bench judge runner (private Space)

Documentation follows ASD-STE100 Simplified Technical English principles. Formal compliance has
not been certified.

This Space resumes the Milestone 5 judge stage on a graphics processing unit (GPU). It runs only
the pending judge steps. It does not run model inference.

> **Warning:** Keep this Space private. The benchmark items are `source_pending`. They have no
> human review. Do not make this Space or the results repository public.

GitHub is the primary source repository: https://github.com/taranrai/LiverSWAT-Bench. This Space
contains only the files in `deploy/hf-space/`. The build clones one exact commit from GitHub.

## Settings

| Name | Type | Value |
| --- | --- | --- |
| `LSB_GIT_REF` | Variable | Full 40-character commit SHA to clone |
| `LSB_RESULTS_REPO` | Variable | Private dataset repository for results, `OWNER/NAME` |
| `HF_TOKEN` | Secret | Token with write access to the results repository and this Space |
| `LSB_SYNC_INTERVAL_S` | Variable (optional) | Seconds between result uploads. Default: 300 |
| `LSB_AUTO_PAUSE` | Variable (optional) | `1` pauses the Space when the judge stage stops. Default: 1 |

The procedure is in `docs/hf-space-judge-migration.md` in the GitHub repository.
