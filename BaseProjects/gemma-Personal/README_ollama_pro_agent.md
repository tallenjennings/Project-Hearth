# Ollama Pro Agent

`ollama_pro_agent.py` is a host-driven desktop and CLI agent for local Ollama models.
It keeps tool execution in Python, while the model only decides when to request a tool.

## Highlights

- Desktop GUI built with Tkinter
- Ollama `/api/chat` integration using `requests`
- JSON-only tool protocol for reliable host-side execution
- Session chat history and live tool log
- Workspace-restricted file tools
- Approval prompts for risky tools such as PowerShell and file writes
- CLI mode is still available

## Included tools

Safe tools enabled by default:

- `get_current_time`
- `get_weather`
- `internet_search`
- `calculator`
- `system_info`
- `list_directory`
- `find_files`
- `read_text_file`
- `hash_file`
- `echo`

Risky tools available but approval-gated:

- `http_get`
- `write_text_file`
- `powershell_access`

## Requirements

- Python 3.11+
- `requests`
- Local Ollama server running
- A local model tag such as `gemma4:eb2` or whatever tag you have installed

Install the only required package:

```powershell
python -m pip install requests
```

## Run the GUI

```powershell
python ollama_pro_agent.py
```

## Run CLI mode

One-shot prompt:

```powershell
python ollama_pro_agent.py --cli "What is the weather in Calgary and summarize the result."
```

Interactive CLI:

```powershell
python ollama_pro_agent.py --cli
```

## Useful CLI flags

```powershell
python ollama_pro_agent.py --cli --model gemma4:eb2 --host http://localhost:11434 --workspace C:\gemma --debug
```

PowerShell is disabled by default in CLI mode. Enable it explicitly if you want it:

```powershell
python ollama_pro_agent.py --cli --enable-powershell
```

## GUI workflow

1. Start Ollama and make sure your model tag is available.
2. Launch the GUI.
3. Set the model name and workspace root.
4. Enable or disable tools from the left panel.
5. Leave `Auto-approve risky tools` off if you want confirmation dialogs.
6. Send a message.

## Notes

- File tools are restricted to the workspace root you select in the GUI or pass in CLI mode.
- The model never directly executes code or reads the machine on its own.
- If your local tag is actually `gemma4:e2b` instead of `gemma4:eb2`, change the model field in the GUI or use `--model`.
