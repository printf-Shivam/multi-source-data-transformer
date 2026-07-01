#!/usr/bin/env python3
import argparse
import json
import sys

from src.extract.ats_parser import parse_ats, load_schema_mapping
from src.extract.github_parser import parse_github
from src.extract.notes_parser import parse_recruiter_note
from src.transform.entity_linker import link_entities
from src.transform.merge_engine import merge_sources
from src.load.projector import project_output, load_config

def main():
    parser = argparse.ArgumentParser(
        description="Eightfold Multi-Source Candidate Data Transformer"
    )
    
    # --- Data Sources ---
    parser.add_argument(
        "--ats",
        required=False,
        help="Path to structured ATS JSON file"
    )
    parser.add_argument(
        "--ats-schema",
        required=False,
        help="Path to ATS schema mapping JSON (optional, uses hardcoded if not provided)"
    )
    parser.add_argument(
        "--github",
        required=False,
        help="GitHub username (optional if --ats is provided with a github_url)"
    )
    parser.add_argument(
        "--note", 
        required=False, 
        help="Path to an unstructured recruiter note (TXT file)"
    )
    
    # --- Pipeline Configuration ---
    parser.add_argument(
        "--config",
        required=True,
        help="Path to runtime config JSON file for dynamic projection"
    )
    parser.add_argument(
        "--output",
        help="Path to output JSON file (optional, prints to stdout if not provided)"
    )
    parser.add_argument(
        "--no-github",
        action="store_true",
        help="Skip live GitHub API calls. Useful for offline runs or bypassing rate limits."
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress logs (only prints final JSON or fatal errors)"
    )

    args = parser.parse_args()

    def log(msg):
        """Helper to print logs to stderr so they don't corrupt stdout JSON."""
        if not args.quiet:
            print(msg, file=sys.stderr)

    # --- 1. Pipeline Validation ---
    has_ats = bool(args.ats)
    has_github = bool(args.github)
    has_note = bool(args.note)

    if not has_ats and not has_github and not has_note:
        print("[Pipeline] ERROR: You must provide at least one source (--ats, --github, or --note).", file=sys.stderr)
        sys.exit(1)

    if args.no_github and has_github and not has_ats and not has_note:
        print("[Pipeline] ERROR: --no-github enabled and no other sources provided. Pipeline has no data to process.", file=sys.stderr)
        sys.exit(1)

    if has_github and not has_ats:
        log("[Pipeline] WARNING: No ATS record provided. GitHub-only data is likely to be dropped during entity linking (missing > wrong).")

    try:
        # --- 2. Extract: Structured ATS Data ---
        ats_obs = []
        if has_ats:
            log("[Pipeline] Extracting structured ATS data...")
            if args.ats_schema:
                schema_mapping = load_schema_mapping(args.ats_schema)
                ats_obs = parse_ats(args.ats, schema_mapping)
            else:
                ats_obs = parse_ats(args.ats)
            
            if not ats_obs:
                log("[Pipeline] WARNING: No ATS data extracted (file may be empty or malformed).")

        # --- 3. Extract: Unstructured Recruiter Note ---
        note_obs = []
        if has_note:
            log("[Pipeline] Extracting unstructured recruiter note...")
            try:
                with open(args.note, 'r', encoding='utf-8') as f:
                    raw_text = f.read()
                    note_obs = parse_recruiter_note(raw_text)
                    log(f"[Pipeline] Extracted {len(note_obs)} observations from note.")
            except Exception as e:
                log(f"[Pipeline] WARNING: Failed to read note file: {e}")

        # --- 4. Extract: GitHub REST API ---
        github_obs = []
        if args.no_github:
            log("[Pipeline] --no-github set: skipping all GitHub API calls.")
        elif has_github:
            log(f"[Pipeline] Extracting GitHub data for @{args.github}...")
            github_obs = parse_github(args.github)
        elif ats_obs:
            # Auto-derive GitHub username if the ATS file provided a URL
            ats_github_url = _find_ats_github_url(ats_obs)
            if ats_github_url:
                derived_username = _extract_github_username_from_url(ats_github_url)
                if derived_username:
                    log(f"[Pipeline] Auto-derived GitHub username from ATS: {derived_username}")
                    log(f"[Pipeline] Extracting GitHub data for @{derived_username}...")
                    github_obs = parse_github(derived_username)

        # --- 5. Entity Linking (Verification) ---
        linked_github = []
        if ats_obs and github_obs:
            log("[Pipeline] Verifying identity across sources (Entity Linking)...")
            linked_github = link_entities(ats_obs, github_obs)
        elif github_obs and not ats_obs:
            log("[Pipeline] Only GitHub data available. Per the orphaned-entity policy, GitHub data is dropped (missing data is safer than an unverified match).")
            linked_github = []

        # --- 6. Merge Engine (Conflict Resolution) ---
        log("[Pipeline] Merging sources and applying Source Authority Matrix...")
        
        # Combine ALL sources into one master list before merging
        # This handles ATS, GitHub, and Note data in one unified stream
        all_observations = ats_obs + linked_github + note_obs
        
        # Now pass the SINGLE list to the source-agnostic merge engine
        profile = merge_sources(all_observations)

        # --- 7. Load & Project (Configurable Output) ---
        log("[Pipeline] Loading runtime configuration...")
        config = load_config(args.config)

        log("[Pipeline] Projecting output to requested schema...")
        output = project_output(profile, config)

        # --- 8. Final Output ---
        json_output = json.dumps(output, indent=2, default=str)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(json_output)
            log(f"[Pipeline] Output written to {args.output}")
        else:
            print(json_output)

    except FileNotFoundError as e:
        print(f"[Pipeline] ERROR: File not found - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[Pipeline] ERROR: {e}", file=sys.stderr)
        sys.exit(1)


# --- Extraction Helpers ---

def _find_ats_github_url(obs):
    for o in obs:
        if o.field == "github_url" and o.value:
            return o.value
    return None


def _extract_github_username_from_url(url):
    import re
    match = re.search(r"github\.com/([^/\s?]+)", url)
    return match.group(1) if match else None


if __name__ == "__main__":
    main()