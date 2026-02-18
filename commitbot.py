#!/usr/bin/env python3
import argparse
import sys
import subprocess
import requests
import json
import os

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
        # Get staged changes
        diff = subprocess.check_output(
            ["git", "diff", "--cached"],
            cwd=repo_path,
            stderr=subprocess.PIPE,
            text=True
        )
        return diff
    except subprocess.CalledProcessError as e:
        print(f"Error getting git diff: {e.stderr}", file=sys.stderr)
        sys.exit(1)

def generate_prompt(diff, format_type):
    """
    Constructs the prompt for the LLM based on the diff and format type.
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
    parser = argparse.ArgumentParser(description="CommitBot: Generate commit messages from staged changes using Ollama.")

    parser.add_argument("path", nargs="?", default=".", help="Path to the git repository (default: current directory)")
    parser.add_argument("--url", default="http://localhost:11434", help="Ollama API URL (default: http://localhost:11434)")
    parser.add_argument("--model", default="mistral", help="Ollama model to use (default: mistral)")
    parser.add_argument("--format", choices=["generate", "split", "emoji"], default="generate", help="Output format (default: generate)")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt and exit without calling Ollama")

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

    prompt = generate_prompt(diff, args.format)

    if not args.dry_run:
        print(f"Generating commit message using model '{args.model}'...", file=sys.stderr)

    commit_msg = call_ollama(args.url, args.model, prompt, dry_run=args.dry_run)

    print(commit_msg)

if __name__ == "__main__":
    main()
