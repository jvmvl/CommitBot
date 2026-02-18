# CommitBot

A command-line tool that generates Conventional Commit messages from your staged Git changes using a local Ollama AI model.

## Features

- **Local AI**: Uses your local Ollama instance (default: `gpt-oss:120b-cloud`)—no data leaves your machine.
- **Context-Aware**: Analyzes staged changes (`git diff --cached`) to generate relevant messages.
- **Auto-Commit**: Can commit changes directly or open your editor with the generated message.
- **Configurable**: Set defaults via `.commitbot.json` in your home or project directory.
- **Smart Filtering**: Automatically ignores lockfiles (`package-lock.json`, `yarn.lock`, etc.) to keep prompts efficient.
- **Interactive Retry**: Don't like the message? Ask CommitBot to try again.
- **Multiple Formats**:
  - `generate`: A standard Conventional Commit.
  - `split`: Breaks down large changes into multiple atomic commits.
  - `emoji`: Adds emojis to the commit type (e.g., ✨ feat, 🐛 fix).
- **Pipe-Friendly**: Outputs only the commit message to stdout, perfect for piping to clipboard.

## Prerequisites

- **Python 3.6+**
- **Git** (available in your PATH)
- **Ollama**: Must be installed and running locally. [Install Ollama](https://ollama.com/).
  - Make sure you have pulled the model (e.g., `ollama pull gpt-oss:120b-cloud`).

## Installation

### 1. Clone or Download
Clone the repository or download `commitbot.py` and `requirements.txt`.
```bash
git clone https://github.com/yourusername/commitbot.git
cd commitbot
```

### 2. Install Dependencies
```bash
# General
pip install -r requirements.txt

# Windows (if using 'py' launcher)
py -m pip install -r requirements.txt
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

### Basic Usage (Default: `gpt-oss:120b-cloud` model, `generate` format)
```bash
commitbot
```

### Commit Automatically
#### Interactive Confirmation (`--commit`)
Review the message in the terminal, then confirm with `y` to commit immediately.
If you don't like the message, type `r` to regenerate it (you can optionally add feedback like "Make it shorter").
```bash
commitbot --commit
```

#### Open in Editor (`--edit`)
Opens your configured git editor (e.g., vim, nano, VS Code) with the generated message pre-filled. You can edit it before saving/committing.
```bash
commitbot --edit
```

### Specify Model
Use a specific model (e.g., `gpt-oss:120b-cloud`, `llama3`):
```bash
commitbot --model gpt-oss:120b-cloud
```

### Configuration File (`.commitbot.json`)
You can set defaults by creating a `.commitbot.json` file in your **home directory** or the **project root**.
Example:
```json
{
  "model": "gpt-oss:120b-cloud",
  "url": "http://localhost:11434",
  "format": "emoji"
}
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

- **"ModuleNotFoundError: No module named 'requests'"**:
  - On Windows, try installing dependencies specifically for the Python version you are running:
    ```bash
    py -m pip install -r requirements.txt
    ```
- **"Error: Model 'gpt-oss:120b-cloud' not found" (404 Error)**:
  - This means the model hasn't been downloaded to Ollama yet.
  - Run `ollama pull gpt-oss:120b-cloud` (or whatever model you want to use).
  - Run `ollama list` to see what models you have available.
- **"No staged changes."**: Make sure you have run `git add <files>` before running CommitBot.
- **Connection Error**: Ensure Ollama is running (`ollama serve`).
- **Large Diff Warning**: If your staged changes are very large (>10k chars), CommitBot will warn you. Consider splitting your changes or using `--format split`.
- **Windows Encoding**: If you see weird characters, try setting `chcp 65001` in your terminal for UTF-8 support.
