"""Synchronise pilot results with a private Hugging Face dataset repository.

Usage:
  python scripts/hf_results_sync.py pull --repo OWNER/NAME --results-dir DIR
  python scripts/hf_results_sync.py push --repo OWNER/NAME --results-dir DIR [--create]
  python scripts/hf_results_sync.py judge-models --config PILOT_CONFIG
  python scripts/hf_results_sync.py pause --space OWNER/NAME

The token comes from the HF_TOKEN environment variable. The script refuses a public
repository. See docs/hf-space-judge-migration.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("pull", "push"):
        p = sub.add_parser(name)
        p.add_argument("--repo", required=True, help="Private dataset repository ID.")
        p.add_argument("--results-dir", required=True, type=Path)
        if name == "push":
            p.add_argument("--create", action="store_true", help="Create a private repository.")
            p.add_argument("--message", default="Sync pilot results")
    p = sub.add_parser("judge-models", help="Print the Ollama model names of the judge models.")
    p.add_argument("--config", required=True, type=Path)
    p = sub.add_parser("pause", help="Pause a Space so that it stops using hardware.")
    p.add_argument("--space", required=True)
    args = parser.parse_args()

    if args.command == "judge-models":
        from liverswat_bench.experiments.pilot import load_pilot_config
        from liverswat_bench.judges.schema import load_judge_config

        cfg = load_pilot_config(args.config)
        paths = [*cfg.judges, *(cfg.prompt_sensitivity.judges if cfg.prompt_sensitivity else [])]
        for name in dict.fromkeys(load_judge_config(p).model.model_name for p in paths):
            print(name)
        return 0

    from huggingface_hub import HfApi

    from liverswat_bench.hf_results import SyncError, pull, push, require_private

    api = HfApi()
    try:
        if args.command == "pull":
            r = pull(api, args.repo, args.results_dir)
            print(
                f"pull: copied {len(r.copied)}, replaced derived {len(r.replaced_derived)}, "
                f"identical {len(r.identical)}, skipped incomplete {len(r.skipped_incomplete)}"
            )
            for rel in r.skipped_incomplete:
                print(f"  skipped incomplete: {rel}")
        elif args.command == "push":
            if args.create:
                require_private(api, args.repo, create=True)
            push(api, args.repo, args.results_dir, args.message)
            print(f"push: {args.results_dir} -> {args.repo}")
        elif args.command == "pause":
            api.pause_space(args.space)
            print(f"paused Space {args.space}")
    except SyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
