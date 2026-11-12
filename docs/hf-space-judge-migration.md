# Milestone 5 judge stage: migration to a Hugging Face Space

Documentation follows ASD-STE100 Simplified Technical English principles. Formal compliance has
not been certified.

This document explains the move of the remaining Milestone 5 judge steps. The steps move from
the laptop to a private Hugging Face Docker Space with a graphics processing unit (GPU).

> **Warning:** The benchmark items are `source_pending`. They have no human review. Keep the
> Space and the results repository private. Do not upload benchmark items or results to a
> public Hugging Face repository.

## Status at the pause

The local judge stage stopped on 12 November 2026 at 23:18 Greenwich Mean Time (GMT). The
process received a termination signal (SIGTERM) after the step `phi4` on
`ollama-llama3.1-8b__oracle` wrote its output. No output file was lost or changed.

| Item | Planned | Complete | Remaining |
| --- | --- | --- | --- |
| Model responses (2 models x 3 conditions x 12 benchmark items) | 72 | 72 | 0 |
| Judge results, prompt `v2` (2 judge models x 72 model responses) | 144 | 72 | 72 |
| Judge results, prompt `v2-alt` (`mistral-nemo`, Condition A, 2 models) | 24 | 12 | 12 |
| **Judge results, total** | **168** | **84** | **84** |

All 84 complete judge results are for `llama3.1-8b`. Of these, 80 have status `ok` and 4 have
status `invalid_output` (all from `mistral-nemo`). The remaining 84 judge results are for
`qwen2.5-7b`.

The recorded duration of the six completed judge steps is 54.6 minutes on the laptop (Apple M4
Pro, 24 gigabytes (GB)). The duration of the remaining steps on the laptop is expected to be
similar.

## What moves and what stays

| Component | Location |
| --- | --- |
| Source code, configuration, benchmark items | GitHub (primary source repository) |
| Model responses and completed judge results | GitHub, in `results/m5-real-model-pilot/` |
| Remaining judge steps | Private Hugging Face Space (`deploy/hf-space/`) |
| Results during the Space run | Private Hugging Face dataset repository (temporary storage) |
| Final results | GitHub, after you download and review them |

The Space does not run model inference. The Space runs `liverswat pilot --judge-only`. This
command stops with an error if a run directory has no model responses or no scores.

## How the evaluation resumes

1. **Step level.** The pilot skips each step that has an output file. The command
   `liverswat pilot --config FILE --judge-only --dry-run` lists the pending steps. It runs and
   writes nothing.
2. **Response level.** During a judge step, each judge result is appended to
   `judgements/<judge_id>.partial.jsonl`. The file `<judge_id>.partial.meta.json` records the
   inputs (judge configuration hash, model responses hash, dataset hash, prompt versions,
   repeats). After an interruption, the next run reuses the stored judge results and judges only
   the remaining model responses. The judge manifest records the count in
   `n_resumed_from_checkpoint`.
3. **Safety checks.** A checkpoint with different inputs is not used and not changed. The run
   stops with an error. A line cut by an interruption is ignored, and that model response is
   judged again.
4. **Atomic output.** The final judge result file and the manifest are written to a temporary file
   and then renamed. A reader never sees a partly written file. The checkpoint files are removed
   only after both files are written.

The dry run on the laptop after the pause gave this result:

```text
Pending steps: 7
  [judge] ollama-mistral-nemo-12b on ollama-qwen2.5-7b__baseline
  [judge] ollama-phi4-14b on ollama-qwen2.5-7b__baseline
  [judge sensitivity] ollama-mistral-nemo-12b on ollama-qwen2.5-7b__baseline
  [judge] ollama-mistral-nemo-12b on ollama-qwen2.5-7b__retrieved
  [judge] ollama-phi4-14b on ollama-qwen2.5-7b__retrieved
  [judge] ollama-mistral-nemo-12b on ollama-qwen2.5-7b__oracle
  [judge] ollama-phi4-14b on ollama-qwen2.5-7b__oracle
```

No inference step and no completed judge step is in the list.

The sensitivity step judges prompts `v2` and `v2-alt` together, in one step. This step again
produces the `v2` judge results for `mistral-nemo` on Condition A. The laptop run of
`llama3.1-8b` used the same procedure. The procedure is not changed.

## Persistent result storage

The Space stores results in a private Hugging Face dataset repository. Free Space hardware has
no persistent disk.

1. At start, the Space downloads the stored results and merges them into the results directory.
2. During the run, the Space uploads the results directory every 300 seconds (setting
   `LSB_SYNC_INTERVAL_S`).
3. At the end, the Space uploads the results again. Then it pauses itself (setting
   `LSB_AUTO_PAUSE`, default `1`), so that the GPU hardware stops.

The merge rules are in `src/liverswat_bench/hf_results.py`:

- A file that is missing locally is copied.
- A derived file (`report/`, `comparison/`, `pilot_summary.*`) is replaced.
- A primary file (model responses, scores, manifests, judge results) that differs is a conflict.
  The pull stops and changes nothing.
- A judge result file is used only if its manifest count matches the number of records.
- Each upload replaces the remote checkpoint files with the local checkpoint files. The
  repository history keeps the earlier versions.

The synchronisation script refuses a public repository. It does not create a repository unless
you give the option `--create`, and then it creates a private repository.

## Procedure

Do steps 1 to 4 yourself. They send content to remote services, and step 4 can cause charges.

1. Merge this change on GitHub. Record the full commit Secure Hash Algorithm (SHA) value that
   contains
   `results/m5-real-model-pilot/`.
2. Create a private dataset repository on Hugging Face for the results. Example:
   `python scripts/hf_results_sync.py push --repo OWNER/lsb-m5-results --results-dir
   results/m5-real-model-pilot --create`.
3. Create a private Docker Space. Copy the four files in `deploy/hf-space/` to the Space
   repository. Set the variables and the secret in the table in `deploy/hf-space/README.md`.
4. Select the GPU hardware in the Space settings. **Get approval before you select paid
   hardware.** The judge models run one at a time. `phi4:14b` (Q4_K_M) needs about 9 GB of GPU
   memory. `mistral-nemo:12b` (Q4_0) needs about 7 GB. The context needs more memory. A GPU with
   16 GB or more is sufficient.
5. Open the Space page. It shows the status log only: the commit, the Ollama version, the GPU,
   the pending steps and the progress lines.
6. When the status log shows `done`, download the results:
   `python scripts/hf_results_sync.py pull --repo OWNER/lsb-m5-results --results-dir
   results/m5-real-model-pilot`.
7. Run `liverswat pilot --config configs/experiments/m5-real-model-pilot.yaml --judge-only
   --dry-run`. Expected outcome: `Pending steps: 0`.
8. Review the results, then commit them to GitHub.

## Reproducibility controls

- The image uses Ollama 0.40.6, the same version as the laptop. The image is pinned by digest.
- The build clones one exact GitHub commit (`LSB_GIT_REF`). The build fails if the SHA is not a
  full 40-character SHA.
- The Ollama adapter refuses to run if the downloaded model digest differs from the digest in
  the judge configuration. If the registry has changed a model tag, the run stops. It does not
  use different weights.
- Each judge manifest records the platform, the processor type, the Ollama version, the library
  versions and the Git state.

## Limitations of the migration

- **Mixed hardware.** The `llama3.1-8b` judge results come from Apple silicon (Metal). The
  `qwen2.5-7b` judge results will come from an NVIDIA GPU (CUDA). Temperature 0 and a fixed seed
  do not guarantee identical output on different hardware. A difference between the two
  evaluated models can therefore include a hardware effect. The manifests identify the host of
  each step. Report the host with each result.
- **Option for one host.** To remove the hardware effect, run all 168 judge results on one host.
  This repeats the 84 completed judge results. It needs your approval because it changes the
  plan and uses more compute.
- **Not tested on Hugging Face.** The Docker image was not built and the Space was not run in
  this milestone. The local Docker daemon was not running. The synchronisation code has unit
  tests with a fake client only.
- **Model download.** The Space has no persistent storage. At each start, it downloads about
  16 GB of judge model weights (9.1 GB and 7.1 GB, as listed by `ollama list`).
