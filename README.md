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
- **Git** (available in your PATH)
- **Ollama**: Must be installed and running locally. [Install Ollama](https://ollama.com/).
  - Make sure you have pulled a model (e.g., `ollama pull mistral` or `ollama pull ministral`).

## Installation

### 1. Clone or Download
Clone the repository or download `commitbot.py` and `requirements.txt`.
```bash
git clone https://github.com/yourusername/commitbot.git
cd commitbot
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup (OS Specific)

#### Windows
You can run it directly with `python commitbot.py`, but to make it easier:
1.  **Add the folder to your PATH** environment variable.
2.  Or copy `commitbot.py` and `commitbot.bat` to a folder already in your PATH (e.g., `C:\Program Files\CommitBot`).
3.  Now you can just type `commitbot` in Command Prompt or PowerShell.

#### macOS / Linux
1.  Make the script executable:
    ```bash
    chmod +x commitbot.py
    ```
2.  Create a symlink to run it from anywhere:
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
If Ollama is running on a different port or host (e.g., WSL to Windows host):
```bash
# Windows / Mac / Linux default
commitbot --url http://localhost:11434

# From WSL2 to Windows host
commitbot --url http://host.docker.internal:11434
```

### Copy to Clipboard
Generate and copy directly to your clipboard:

**Windows (PowerShell / CMD)**
```powershell
commitbot | clip
```

**macOS**
```bash
commitbot | pbcopy
```

**Linux (xclip)**
```bash
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
- **Windows Encoding**: If you see weird characters, try setting `chcp 65001` in your terminal for UTF-8 support.
