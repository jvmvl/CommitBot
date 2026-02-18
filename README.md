# CommitBot

A command-line tool that generates Conventional Commit messages from your staged Git changes using a local Ollama AI model.

## Features

- **Local AI**: Uses your local Ollama instance (default: `mistral`)—no data leaves your machine.
- **Context-Aware**: Analyzes staged changes (`git diff --cached`) to generate relevant messages.
- **Multiple Formats**:
  - `generate`: A standard Conventional Commit.
  - `split`: Breaks down large changes into multiple atomic commits.
  - `emoji`: Adds emojis to the commit type (e.g., ✨ feat, 🐛 fix).
- **Pipe-Friendly**: Outputs only the commit message to stdout, perfect for piping to clipboard.

## Prerequisites

- **Python 3.6+**
- **Git**
- **Ollama**: Must be installed and running locally. [Install Ollama](https://ollama.com/).
  - Make sure you have pulled a model (e.g., `ollama pull mistral` or `ollama pull ministral`).

## Installation

1.  **Clone the repository** (or download `commitbot.py`):
    ```bash
    git clone https://github.com/yourusername/commitbot.git
    cd commitbot
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Make executable**:
    ```bash
    chmod +x commitbot.py
    ```

4.  **(Optional) Add to your PATH**:
    To run `commitbot` from anywhere, create a symlink:
    ```bash
    sudo ln -s $(pwd)/commitbot.py /usr/local/bin/commitbot
    ```

## Usage

Stage your changes first:
```bash
git add .
```

Then run CommitBot:

### Basic Usage (Default: `mistral` model, `generate` format)
```bash
commitbot
```

### Specify Model
Use a specific model (e.g., `ministral`, `llama3`):
```bash
commitbot --model ministral
```

### Output Formats

**Standard Conventional Commit:**
```bash
commitbot --format generate
```

**Split Commits (for large changes):**
```bash
commitbot --format split
```

**Emoji Style:**
```bash
commitbot --format emoji
```

### Custom Ollama URL
If Ollama is running on a different port or host:
```bash
commitbot --url http://192.168.1.50:11434
```

### Copy to Clipboard (macOS/Linux)
Generate and copy directly to your clipboard:
```bash
# macOS
commitbot | pbcopy

# Linux (xclip)
commitbot | xclip -selection clipboard
```

### Dry Run
Preview the prompt without calling the API:
```bash
commitbot --dry-run
```

## Troubleshooting

- **"No staged changes."**: Make sure you have run `git add <files>` before running CommitBot.
- **Connection Error**: Ensure Ollama is running (`ollama serve`).
- **Large Diff Warning**: If your staged changes are very large (>10k chars), CommitBot will warn you. Consider splitting your changes or using `--format split`.
