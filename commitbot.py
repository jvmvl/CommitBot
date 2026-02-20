#!/usr/bin/env python3
import argparse
import sys
import subprocess
import requests
import json
import os
import tempfile
import re
from pathlib import Path
import colorama
from colorama import Fore, Style

# Initialize colorama
colorama.init()

VERSION = "1.0.0"

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
Return a VALID JSON array of objects. Do not include markdown formatting like ```json.
Each object must have:
- "message": The commit message (string).
- "files": A list of file paths (strings) included in this commit.

Example:
[
  {
    "message": "feat(auth): add login",
    "files": ["src/auth.ts", "src/login.html"]
  },
  {
    "message": "fix(ui): fix button color",
    "files": ["src/styles.css"]
  }
]
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

def print_error(msg):
    print(f"{Fore.RED}{msg}{Style.RESET_ALL}", file=sys.stderr)

def print_warning(msg):
    print(f"{Fore.YELLOW}{msg}{Style.RESET_ALL}", file=sys.stderr)

def print_info(msg):
    print(f"{Fore.CYAN}{msg}{Style.RESET_ALL}", file=sys.stderr)

def print_success(msg):
    print(f"{Fore.GREEN}{msg}{Style.RESET_ALL}", file=sys.stdout) # Note: Success usually goes to stdout

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
            print_warning(f"Warning: Could not parse config file at {home_config_path}")

    # Check current directory (higher priority)
    local_config_path = Path.cwd() / ".commitbot.json"
    if local_config_path.exists():
        try:
            with open(local_config_path, "r") as f:
                config.update(json.load(f))
        except json.JSONDecodeError:
             print_warning(f"Warning: Could not parse config file at {local_config_path}")

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
        print_error(f"Error: '{repo_path}' is not a git repository.")
        sys.exit(1)
    except FileNotFoundError:
        print_error("Error: 'git' command not found.")
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
        print_error(f"Error getting git diff: {e.stderr}")
        sys.exit(1)

def get_staged_files(repo_path):
    """
    Get a list of staged files.
    """
    try:
        files = subprocess.check_output(
            ["git", "diff", "--name-only", "--cached"],
            cwd=repo_path,
            text=True
        ).strip().splitlines()
        return files
    except subprocess.CalledProcessError:
        return []

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
        prompt += '\n\nCOMMAND: "generate split" (Output ONLY the JSON array)'
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
        print(f"{Fore.MAGENTA}--- DRY RUN: Generated Prompt ---{Style.RESET_ALL}")
        print(prompt)
        print(f"{Fore.MAGENTA}---------------------------------{Style.RESET_ALL}")
        return "Dry run: No API call made."

    api_url = f"{url}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2 # Low temperature for consistent JSON
        }
    }

    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "")
    except requests.exceptions.ConnectionError:
        print_error(f"Error: Could not connect to Ollama at {url}. Is it running?")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print_error(f"Error: Model '{model}' not found. (404 Not Found)")
            print_info(f"Tip: Run 'ollama pull {model}' to install it.")
            print_info(f"     Or use a different model with '--model <name>'.")

            # Try to list available models
            try:
                tags_response = requests.get(f"{url}/api/tags")
                tags_response.raise_for_status()
                models = [m['name'] for m in tags_response.json().get('models', [])]
                if models:
                    print_info(f"     Available models: {', '.join(models)}")
            except:
                pass # Ignore errors when trying to help
        else:
            print_error(f"Error calling Ollama API: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print_error(f"Error calling Ollama API: {e}")
        sys.exit(1)

def extract_json(text):
    """
    Extracts a JSON list from the text, handling markdown code blocks.
    """
    text = text.strip()
    # Remove markdown code blocks if present
    match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if match:
        text = match.group(1)
    elif text.startswith("```") and text.endswith("```"):
         text = text.strip("`").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None

def execute_smart_split(plan, repo_path, all_staged_files):
    """
    Executes the split commit plan.
    """
    print_info("Unstaging all files to prepare for split commits...")
    subprocess.run(["git", "restore", "--staged", "."], cwd=repo_path, check=True)

    staged_files_start = set(all_staged_files)
    committed_files = set()

    for i, commit in enumerate(plan, 1):
        message = commit.get('message')
        files = commit.get('files', [])

        if not files:
            print_warning(f"Skipping Commit {i}: No files specified.")
            continue

        print_info(f"Processing Commit {i}: {message.splitlines()[0]}...")

        # Stage specific files
        try:
            subprocess.run(["git", "add"] + files, cwd=repo_path, check=True)
        except subprocess.CalledProcessError:
            print_error(f"Failed to stage files for commit {i}. Skipping.")
            continue

        # Commit
        try:
            subprocess.run(["git", "commit", "-m", message], cwd=repo_path, check=True)
            print_success(f"Commit {i} created.")
            committed_files.update(files)
        except subprocess.CalledProcessError:
            print_error(f"Failed to create commit {i}.")

    # Check for leftover files
    leftover = staged_files_start - committed_files
    if leftover:
        # Re-stage leftovers so user doesn't lose track of them
        try:
            subprocess.run(["git", "add"] + list(leftover), cwd=repo_path, check=True, stderr=subprocess.DEVNULL)
            print_warning(f"Warning: The following files were NOT committed and have been re-staged: {', '.join(leftover)}")
        except:
             print_warning(f"Warning: The following files were NOT committed: {', '.join(leftover)}")

def main():
    # Load config
    config = load_config()

    # Defaults
    default_url = config.get("url", "http://localhost:11434")
    default_model = config.get("model", "gpt-oss:120b-cloud")
    default_format = config.get("format", "generate")

    parser = argparse.ArgumentParser(description="CommitBot: Generate commit messages from staged changes using Ollama.")

    parser.add_argument("path", nargs="?", default=".", help="Path to the git repository (default: current directory)")
    parser.add_argument("--url", default=default_url, help=f"Ollama API URL (default: {default_url})")
    parser.add_argument("--model", default=default_model, help=f"Ollama model to use (default: {default_model})")
    parser.add_argument("--format", choices=["generate", "split", "emoji"], default=default_format, help=f"Output format (default: {default_format})")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt and exit without calling Ollama")
    parser.add_argument("--version", action="store_true", help="Print version information")

    # New flags for commit functionality
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--commit", action="store_true", help="Confirm and commit the generated message immediately.")
    group.add_argument("--edit", action="store_true", help="Open the generated message in your editor before committing.")

    args = parser.parse_args()

    if args.version:
        print(f"CommitBot v{VERSION}")
        sys.exit(0)

    repo_path = os.path.abspath(args.path)

    if not os.path.isdir(repo_path):
        print_error(f"Error: Directory '{repo_path}' not found.")
        sys.exit(1)

    print_info(f"Checking for staged changes in {repo_path}...")
    diff = get_staged_diff(repo_path)
    current_staged_files = get_staged_files(repo_path)

    if not diff.strip():
        print_warning("No staged changes.")
        return

    # Warning for large diffs
    if len(diff) > 10000:
        print_warning(f"Warning: Large diff detected ({len(diff)} characters). Results might be truncated or less accurate.")

    # Interactive generation and retry loop
    prompt_suffix = None

    while True:
        prompt = generate_prompt(diff, args.format, feedback=prompt_suffix)

        if not args.dry_run:
            if prompt_suffix:
                print_info(f"Regenerating commit message...")
            else:
                print_info(f"Generating commit message using model '{args.model}'...")

        response_text = call_ollama(args.url, args.model, prompt, dry_run=args.dry_run)

        if args.dry_run:
            if response_text:
                 print(response_text)
            return

        # Handle Output based on format
        if args.format == "split":
            json_plan = extract_json(response_text)

            if not json_plan or not isinstance(json_plan, list):
                print_error("Error: Failed to parse JSON plan from model response.")
                print_info("Raw response:")
                print(response_text)

                # Allow user to retry if parsing failed
                if args.commit:
                    choice = input(f"{Fore.YELLOW}Parsing failed. Do you want to retry generation? [y/N] {Style.RESET_ALL}").strip().lower()
                    if choice == 'y':
                        prompt_suffix = "Previous response was not valid JSON. Please return strictly valid JSON array."
                        continue
                break

            print(f"\n{Fore.MAGENTA}--- Proposed Split Commit Plan ---{Style.RESET_ALL}")
            for i, item in enumerate(json_plan, 1):
                print(f"{Fore.CYAN}Commit {i}:{Style.RESET_ALL} {item.get('message', 'No message').splitlines()[0]}")
                files_list = item.get('files', [])
                if len(files_list) > 3:
                     print(f"  Files: {', '.join(files_list[:3])}, ... (+{len(files_list)-3} more)")
                else:
                     print(f"  Files: {', '.join(files_list)}")
            print(f"{Fore.MAGENTA}------------------------------------{Style.RESET_ALL}")

            if args.commit:
                try:
                    choice = input(f"{Fore.YELLOW}Do you want to EXECUTE this split plan? [y/N/r] {Style.RESET_ALL}").strip().lower()
                    if choice == 'y':
                        execute_smart_split(json_plan, repo_path, current_staged_files)
                        break
                    elif choice == 'r':
                        user_input = input(f"{Fore.CYAN}Optional feedback (press Enter to just retry): {Style.RESET_ALL}").strip()
                        prompt_suffix = user_input if user_input else "Please regenerate the split plan."
                        continue
                    else:
                        print_warning("Operation aborted.")
                        break
                except KeyboardInterrupt:
                    print_warning("\nAborted.")
                    sys.exit(1)
            else:
                 # Standard output (just print JSON for piping/inspection)
                 print(json.dumps(json_plan, indent=2))
                 break

        else:
            # Standard "generate" or "emoji" flow (Single Commit)
            commit_msg = response_text

            # Main interaction loop
            if args.commit:
                print(f"\n{Fore.MAGENTA}--- Generated Commit Message ---{Style.RESET_ALL}")
                print(commit_msg)
                print(f"{Fore.MAGENTA}--------------------------------{Style.RESET_ALL}")
                try:
                    choice = input(f"{Fore.YELLOW}Do you want to commit with this message? [y/N/r] {Style.RESET_ALL}").strip().lower()
                    if choice == 'y':
                        subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_path, check=True)
                        print_success("Committed successfully.")
                        break
                    elif choice == 'r':
                        user_input = input(f"{Fore.CYAN}Optional feedback (press Enter to just retry): {Style.RESET_ALL}").strip()
                        prompt_suffix = user_input if user_input else "Please regenerate a better commit message."
                        continue
                    else:
                        print_warning("Commit aborted.")
                        break
                except KeyboardInterrupt:
                    print_warning("\nAborted.")
                    sys.exit(1)
                except subprocess.CalledProcessError as e:
                     print_error(f"Error executing git commit: {e}")
                     sys.exit(1)

            elif args.edit:
                # Edit mode: generate -> open editor -> commit
                with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as tf:
                    tf.write(commit_msg)
                    temp_path = tf.name

                try:
                    print_info("Opening editor for review...")
                    subprocess.run(["git", "commit", "-e", "-F", temp_path], cwd=repo_path, check=True)
                    print_success("Committed successfully.")
                except subprocess.CalledProcessError as e:
                     print_error(f"Error executing git commit: {e}")
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
