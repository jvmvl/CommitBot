#!/usr/bin/env python3
import argparse
import sys
import subprocess
import requests
import json
import os
import tempfile
from pathlib import Path

# --- Prompt Templates ---

BASE_SYSTEM_PROMPT = """You are CommitBot.

SCOPE
Work ONLY from the Git STAGED changes in this workspace (ignore unstaged).
If nothing is staged, reply exactly: "No staged changes."

RULES
Detect type: feat, fix, refactor, perf, docs, test, chore, build, ci.
Scope = main area (e.g., admin/applications, migrations, car-sharing).
Subject: imperative, <= 72 chars, no trailing period.
Body: 2–6 bullets; include WHY + key files/functions/tickets; call out tests/migrations/config.
If there’s a breaking change, add:
BREAKING CHANGE: <details>
"""

FORMAT_GENERATE = """
TRIGGERS
"generate" → one Conventional Commit with a short body.

FORMATS
(For "generate")
<type>(<scope>): <summary>

<bullet>
<bullet>
[optional] BREAKING CHANGE: <details>
"""

FORMAT_SPLIT = """
TRIGGERS
"generate split" → 1–5 Conventional Commits grouped by concern (e.g., controllers/models/migrations/frontend); put any schema/migration in its own commit.

FORMATS
(For "generate split")

Commit 1
<type>(<scope>): <summary>

<bullet>
<bullet>

Commit 2
<type>(<scope>): <summary>

<bullet>
"""

FORMAT_EMOJI = """
TRIGGERS
"generate emoji" → same as "generate" but with emoji (✨ feat / 🐛 fix / ♻️ refactor / ⚡ perf / 📝 docs / ✅ test / 🔧 chore).

FORMATS
(For "generate emoji")
<emoji> <type>(<scope>): <summary>

<bullet>
<bullet>
"""

# --- Functions ---

def load_config():
    """
    Loads configuration from .commitbot.json in the current directory or home directory.
    """
    config = {}

    # Check home directory first (lower priority)
    home_config_path = Path.home() / ".commitbot.json"
    if home_config_path.exists():
        try:
            with open(home_config_path, "r") as f:
                config.update(json.load(f))
        except json.JSONDecodeError:
            print(f"Warning: Could not parse config file at {home_config_path}", file=sys.stderr)

    # Check current directory (higher priority)
    local_config_path = Path.cwd() / ".commitbot.json"
    if local_config_path.exists():
        try:
            with open(local_config_path, "r") as f:
                config.update(json.load(f))
        except json.JSONDecodeError:
             print(f"Warning: Could not parse config file at {local_config_path}", file=sys.stderr)

    return config

def get_staged_diff(repo_path):
    """
    Get the staged git diff from the specified repository path.
    """
    try:
        # Check if it's a git repo first
        subprocess.check_output(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_path,
            stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        print(f"Error: '{repo_path}' is not a git repository.", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'git' command not found.", file=sys.stderr)
        sys.exit(1)

    try:
        # Get staged changes, excluding lockfiles
        # We use ':(exclude)' pathspec magic for this
        cmd = ["git", "diff", "--cached", ".",
               ":(exclude)package-lock.json",
               ":(exclude)yarn.lock",
               ":(exclude)pnpm-lock.yaml",
               ":(exclude)composer.lock",
               ":(exclude)Gemfile.lock",
               ":(exclude)poetry.lock"]

        diff = subprocess.check_output(
            cmd,
            cwd=repo_path,
            stderr=subprocess.PIPE,
            text=True
        )
        return diff
    except subprocess.CalledProcessError as e:
        print(f"Error getting git diff: {e.stderr}", file=sys.stderr)
        sys.exit(1)

def generate_prompt(diff, format_type, feedback=None):
    """
    Constructs the prompt for the LLM based on the diff and format type.
    Optionally includes feedback for regeneration.
    """
    prompt = BASE_SYSTEM_PROMPT

    if format_type == "generate":
        prompt += FORMAT_GENERATE
    elif format_type == "split":
        prompt += FORMAT_SPLIT
    elif format_type == "emoji":
        prompt += FORMAT_EMOJI

    prompt += "\n\nHere are the staged changes:\n\n"
    prompt += diff

    # Append the trigger command to ensure the model knows what to do
    if format_type == "generate":
        prompt += '\n\nCOMMAND: "generate" (Output ONLY the commit message)'
    elif format_type == "split":
        prompt += '\n\nCOMMAND: "generate split" (Output ONLY the grouped commit messages)'
    elif format_type == "emoji":
        prompt += '\n\nCOMMAND: "generate emoji" (Output ONLY the commit message with emoji)'

    if feedback:
        prompt += f"\n\nUSER FEEDBACK (Refine the previous message based on this): {feedback}"

    return prompt

def call_ollama(url, model, prompt, dry_run=False):
    """
    Calls the Ollama API to generate the commit message.
    """
    if dry_run:
        print("--- DRY RUN: Generated Prompt ---")
        print(prompt)
        print("---------------------------------")
        return "Dry run: No API call made."

    api_url = f"{url}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "")
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to Ollama at {url}. Is it running?", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Error: Model '{model}' not found. (404 Not Found)", file=sys.stderr)
            print(f"Tip: Run 'ollama pull {model}' to install it.", file=sys.stderr)
            print(f"     Or use a different model with '--model <name>'.", file=sys.stderr)

            # Try to list available models
            try:
                tags_response = requests.get(f"{url}/api/tags")
                tags_response.raise_for_status()
                models = [m['name'] for m in tags_response.json().get('models', [])]
                if models:
                    print(f"     Available models: {', '.join(models)}", file=sys.stderr)
            except:
                pass # Ignore errors when trying to help
        else:
            print(f"Error calling Ollama API: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama API: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    # Load config
    config = load_config()

    # Defaults
    default_url = config.get("url", "http://localhost:11434")
    default_model = config.get("model", "mistral")
    default_format = config.get("format", "generate")

    parser = argparse.ArgumentParser(description="CommitBot: Generate commit messages from staged changes using Ollama.")

    parser.add_argument("path", nargs="?", default=".", help="Path to the git repository (default: current directory)")
    parser.add_argument("--url", default=default_url, help=f"Ollama API URL (default: {default_url})")
    parser.add_argument("--model", default=default_model, help=f"Ollama model to use (default: {default_model})")
    parser.add_argument("--format", choices=["generate", "split", "emoji"], default=default_format, help=f"Output format (default: {default_format})")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt and exit without calling Ollama")

    # New flags for commit functionality
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--commit", action="store_true", help="Confirm and commit the generated message immediately.")
    group.add_argument("--edit", action="store_true", help="Open the generated message in your editor before committing.")

    args = parser.parse_args()

    repo_path = os.path.abspath(args.path)

    if not os.path.isdir(repo_path):
        print(f"Error: Directory '{repo_path}' not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Checking for staged changes in {repo_path}...", file=sys.stderr)
    diff = get_staged_diff(repo_path)

    if not diff.strip():
        print("No staged changes.", file=sys.stderr)
        return

    # Warning for large diffs
    if len(diff) > 10000:
        print(f"Warning: Large diff detected ({len(diff)} characters). Results might be truncated or less accurate.", file=sys.stderr)

    # Interactive generation and retry loop
    prompt_suffix = None

    while True:
        prompt = generate_prompt(diff, args.format, feedback=prompt_suffix)

        if not args.dry_run:
            if prompt_suffix:
                print(f"Regenerating commit message...", file=sys.stderr)
            else:
                print(f"Generating commit message using model '{args.model}'...", file=sys.stderr)

        commit_msg = call_ollama(args.url, args.model, prompt, dry_run=args.dry_run)

        if args.dry_run:
            if commit_msg:
                 print(commit_msg)
            return

        # Main interaction loop
        if args.commit:
            print("\n--- Generated Commit Message ---")
            print(commit_msg)
            print("--------------------------------")
            try:
                choice = input("Do you want to commit with this message? [y/N/r] ").strip().lower()
                if choice == 'y':
                    subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_path, check=True)
                    print("Committed successfully.")
                    break
                elif choice == 'r':
                    user_input = input("Optional feedback (press Enter to just retry): ").strip()
                    prompt_suffix = user_input if user_input else "Please regenerate a better commit message."
                    continue
                else:
                    print("Commit aborted.")
                    break
            except KeyboardInterrupt:
                print("\nAborted.")
                sys.exit(1)
            except subprocess.CalledProcessError as e:
                 print(f"Error executing git commit: {e}", file=sys.stderr)
                 sys.exit(1)

        elif args.edit:
            # Edit mode: generate -> open editor -> commit
            # We don't support retry loop here easily because 'edit' implies handing off control to the editor.

            # Create a temporary file with the commit message
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as tf:
                tf.write(commit_msg)
                temp_path = tf.name

            try:
                print("Opening editor for review...")
                subprocess.run(["git", "commit", "-e", "-F", temp_path], cwd=repo_path, check=True)
                print("Committed successfully.")
            except subprocess.CalledProcessError as e:
                 print(f"Error executing git commit: {e}", file=sys.stderr)
                 sys.exit(1)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            break

        else:
            # Standard output mode
            print(commit_msg)
            break

if __name__ == "__main__":
    main()
