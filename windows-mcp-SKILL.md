---
name: windows-mcp
description: |
  Give Claude direct control of a Windows PC — screenshots, clicking, typing, keyboard shortcuts,
  launching and switching apps, PowerShell, filesystem, registry, clipboard, and process management —
  via the windows-mcp MCP server (CursorTouch/Windows-MCP).
  Use this skill when the user wants to: set up, install, register, or reconnect Windows GUI control /
  desktop automation / computer use on a Windows machine; add windows-mcp to Claude Desktop or Claude
  Code; troubleshoot a windows-mcp server that will not start or does not appear; or when they ask what
  Windows automation tools are available and how to drive them.
  Covers install, config file locations (including the Microsoft Store / MSIX gotcha), the full
  20-tool reference with exact parameter names, safety controls, and uninstall.
license: MIT
metadata:
  upstream: https://github.com/CursorTouch/Windows-MCP
  package: https://pypi.org/project/windows-mcp/
  verified-against: windows-mcp 0.8.5
  version: "1.0"
---

# Windows-MCP — GUI control for Claude on Windows

Registers [`windows-mcp`](https://github.com/CursorTouch/Windows-MCP) (CursorTouch, MIT) as an MCP
server so Claude can see and drive a Windows desktop: screenshots, the UI accessibility tree, mouse and
keyboard, apps, processes, PowerShell, filesystem, and registry.

## Read this first — what this can and cannot do

`windows-mcp` runs over **stdio**, which means the MCP client spawns it as a **child process on the same
machine**. There is no address and no port to connect to.

| Where Claude is running | Can it reach this server? |
|---|---|
| Claude Desktop on the Windows PC | **Yes** |
| Claude Code in a terminal on the Windows PC | **Yes** |
| Claude Code via Remote Control (`claude --remote-control`, driven from claude.ai or the mobile app) | **Yes** — the session is still local, only the UI is remote |
| A cloud session (claude.ai/code web sessions, GitHub Actions, scheduled/remote runs) | **No** |

A cloud session runs in an Anthropic-managed VM. If it reads a stdio entry from a repo's `.mcp.json`, it
spawns that server **inside the cloud VM**, not on the user's PC. So this skill makes setup fast on *any
Windows device*; it does not let a cloud session reach a particular PC. If the user genuinely wants to
drive their PC from a phone or browser, point them at **Remote Control**, not at this file. There is also
a network-transport option below, but it carries real exposure — read that section before suggesting it.

## ⚠️ Before installing

This gives an AI assistant the same power over the PC that the logged-in user has. Not sandboxed, not
read-only.

**It can** run any PowerShell command, read/write/delete any file the account can touch, edit the
registry, kill processes, and synthesize mouse and keyboard input. Synthetic keystrokes mean it can click
"Allow", approve prompts, and confirm irreversible actions — to the OS, it *is* the user at the keyboard.
There is no dry run and no undo.

**The main risk is prompt injection.** `Scrape` and the browser DOM reader pull in text nobody vetted,
and that text lands in the same context as the user's instructions. A hidden line in a web page, GitHub
issue, or email can become a real command: run this script, open the password manager, paste the vault
into this form. Nothing is "exploited" — the model just follows text.

**Assume everything on the machine is reachable:** screen, clipboard, logged-in browser sessions (cookies
mean no password and no MFA prompt is needed), SSH and cloud keys, work email. Revoking access later
means *rotating credentials*, not just uninstalling.

Ranked mitigations:

1. **Prefer a disposable VM** with throwaway accounts, no host-drive sharing, and a snapshot taken before
   each session. This is the only mitigation that still works if the model is fully hijacked.
2. **Do not combine web reading with autonomous action.** Use `--exclude-tools` (below) to drop either
   `Scrape` or `PowerShell,Registry,FileSystem` — not both live at once.
3. **Keep approvals manual.** No auto-approve for `PowerShell`, `Registry`, `FileSystem`, `Process`.
   Never leave it running unattended.
4. **Shrink what is reachable first**: lock the password vault, sign out of banking/cloud consoles, use a
   browser profile with no saved logins, clear the clipboard.
5. **Run as a standard user, never elevated**, and never launch the client as Administrator.
6. Avoid domain-joined or VPN-connected work machines — that is usually a policy violation regardless of
   outcome, and the device-trust posture can pivot into corporate SaaS. Ask the endpoint owner first.

The config written by this skill contains **no secrets** — it is a command and two arguments.

## Prerequisites

- **Windows 10 or 11.** (The README badge claims Windows 7–11; PyPI classifiers list only 10 and 11, and
  the Python floor makes 7/8 implausible. Treat 10/11 as the supported set.)
- **Python 3.13+.** Upstream is inconsistent here — README says 3.13+, the published 0.8.5 metadata says
  `>=3.12`, and `main` has moved to `>=3.14`. `uvx` provisions a suitable interpreter automatically, so
  this usually does not matter.
- **[uv](https://docs.astral.sh/uv/)** — provides `uvx`. The installer below adds it if missing.
- English as the Windows display language is preferred; otherwise exclude the `App` tool, which matches
  Start Menu entries by name.

## Setup

### Claude Code (one command)

```powershell
claude mcp add --scope user windows-mcp -- uvx windows-mcp serve
```

`--scope user` makes it available in every project on this machine. Everything after `--` is passed
through untouched. Verify with `claude mcp list` and `claude mcp get windows-mcp`.

> WSL cannot spawn Windows processes directly — bridge through PowerShell:
> ```bash
> claude mcp add windows-mcp --scope user -- powershell.exe -Command "$env:USERPROFILE\.local\bin\uvx.exe windows-mcp serve"
> ```

### Claude Desktop (edit the config)

Open **Settings → Developer → Edit Config**, or edit the file directly, and merge in:

```json
{
  "mcpServers": {
    "windows-mcp": {
      "command": "uvx",
      "args": ["windows-mcp", "serve"]
    }
  }
}
```

Then **fully quit and reopen Claude Desktop** — closing to the tray is not enough.

#### Config file location

| Install type | Path |
|---|---|
| Standard (installer `.exe`) | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Microsoft Store / MSIX / WinGet** | `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json` |

**This is the single most common reason setup silently fails.** MSIX virtualizes `%APPDATA%`, but the
"Edit Config" button uses a call that bypasses that redirection — so the user edits one file while the app
reads another, and the server never appears with no error shown. The MSIX path is documented by
Windows-MCP upstream and corroborated by Claude Desktop bug reports, but it is *not* in Anthropic's
official docs, so derive the package folder at runtime rather than trusting the `pzs8sxrjxfjjc` hash:

```powershell
Get-AppxPackage -Name *Claude* | Select-Object Name, PackageFamilyName
```

Two further MSIX consequences:

- **The sandboxed app does not inherit `PATH`,** so bare `"command": "uvx"` fails. Use an absolute path:
  ```json
  {
    "mcpServers": {
      "windows-mcp": {
        "command": "C:\\Users\\<user>\\.local\\bin\\uvx.exe",
        "args": ["windows-mcp", "serve"]
      }
    }
  }
  ```
  Backslashes must be doubled in JSON. Using the absolute path is harmless on non-MSIX installs too, so
  when in doubt, always use it.
- A `PATH` edit made after Claude Desktop (or its parent Explorer) started is invisible to it. Sign out
  and back in, or use the absolute path.

### Optional: install from source

```json
{
  "mcpServers": {
    "windows-mcp": {
      "command": "uv",
      "args": ["--directory", "<path to the windows-mcp directory>", "run", "windows-mcp", "serve"]
    }
  }
}
```

Note this embeds an absolute path containing the Windows username — do not commit it to a public repo.

## Automated setup (PowerShell)

Configures Claude Desktop on a machine that does not have it yet. Run as the normal user — **not**
elevated. It resolves an absolute `uvx.exe` path (avoiding both the MSIX `PATH` problem and any need to
modify `PATH`), backs up any existing config, refuses to overwrite a config it cannot parse, and writes
BOM-free UTF-8 so Claude Desktop's JSON parser accepts it.

```powershell
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$ServerName = 'windows-mcp'

# JSON -> ordered dictionary. ConvertFrom-Json -AsHashtable does not exist on Windows PowerShell 5.1.
function ConvertTo-OrderedDict {
    param($InputObject)
    if ($InputObject -is [System.Management.Automation.PSCustomObject]) {
        $d = [ordered]@{}
        foreach ($p in $InputObject.PSObject.Properties) { $d[$p.Name] = ConvertTo-OrderedDict $p.Value }
        return $d
    }
    if ($InputObject -is [System.Collections.IEnumerable] -and $InputObject -isnot [string]) {
        return @(foreach ($item in $InputObject) { ConvertTo-OrderedDict $item })
    }
    return $InputObject
}

# 1. Locate uvx.exe, installing uv if needed.
$uvx = (Get-Command uvx.exe -ErrorAction SilentlyContinue).Source
if (-not $uvx) { $uvx = Join-Path $env:USERPROFILE '.local\bin\uvx.exe' }
if (-not (Test-Path -LiteralPath $uvx)) {
    Write-Host 'Installing uv...' -ForegroundColor Yellow
    powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
        -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $uvx = Join-Path $env:USERPROFILE '.local\bin\uvx.exe'
}
if (-not (Test-Path -LiteralPath $uvx)) {
    throw "uvx.exe not found. Install uv manually: https://docs.astral.sh/uv/getting-started/installation/"
}
Write-Host "Using: $uvx" -ForegroundColor Green

# 2. Build the target list: standard install, plus the MSIX path if a packaged Claude is present.
$targets = @(Join-Path $env:APPDATA 'Claude\claude_desktop_config.json')
$pkg = Get-AppxPackage -Name '*Claude*' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pkg) {
    $targets += Join-Path $env:LOCALAPPDATA `
        ('Packages\{0}\LocalCache\Roaming\Claude\claude_desktop_config.json' -f $pkg.PackageFamilyName)
    Write-Host "Detected MSIX package: $($pkg.PackageFamilyName)" -ForegroundColor Green
}

$entry = [ordered]@{ command = $uvx; args = @('windows-mcp', 'serve') }

foreach ($file in $targets) {
    try {
        $dir = Split-Path -Parent $file
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

        $data = [ordered]@{}
        if (Test-Path -LiteralPath $file) {
            $raw = [System.IO.File]::ReadAllText($file)   # also strips a BOM on read
            if (-not [string]::IsNullOrWhiteSpace($raw)) {
                try { $data = ConvertTo-OrderedDict ($raw | ConvertFrom-Json) }
                catch { Write-Warning "Cannot parse $file - leaving it untouched."; continue }
            }
            Copy-Item -LiteralPath $file -Destination "$file.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')" -Force
        }

        if (-not $data.Contains('mcpServers') -or $data['mcpServers'] -isnot [System.Collections.IDictionary]) {
            $data['mcpServers'] = [ordered]@{}
        }
        $data['mcpServers'][$ServerName] = $entry

        # Write BOM-free UTF-8 via a temp file, then rename, so an interrupted run cannot truncate the config.
        $tmp = "$file.tmp$PID"
        [System.IO.File]::WriteAllText($tmp, ($data | ConvertTo-Json -Depth 32),
            (New-Object System.Text.UTF8Encoding($false)))
        Move-Item -LiteralPath $tmp -Destination $file -Force
        Write-Host "Updated: $file" -ForegroundColor Green
    }
    catch { Write-Warning "Failed on ${file}: $($_.Exception.Message)" }
}

# 3. Claude Code, if present.
if (Get-Command claude -ErrorAction SilentlyContinue) {
    & { $ErrorActionPreference = 'Continue'; claude mcp remove $ServerName -s user *> $null }
    claude mcp add --scope user $ServerName -- $uvx windows-mcp serve
    $global:LASTEXITCODE = 0
}

Write-Host "`nDone. Fully quit and reopen Claude Desktop." -ForegroundColor Cyan
```

Backups are written next to the config as `claude_desktop_config.json.bak-<timestamp>`.

## Restricting which tools are exposed

The most effective safety lever. Whitelist or blacklist at launch:

```powershell
uvx windows-mcp serve --tools "Screenshot,Snapshot,Click,Type,Shortcut,App"   # allow only these
uvx windows-mcp serve --exclude-tools "PowerShell,Registry,FileSystem,Process"  # drop the dangerous ones
```

Equivalent environment variables: `WINDOWS_MCP_TOOLS`, `WINDOWS_MCP_EXCLUDE_TOOLS`.

In `claude_desktop_config.json`, append to `args`:

```json
{
  "mcpServers": {
    "windows-mcp": {
      "command": "C:\\Users\\<user>\\.local\\bin\\uvx.exe",
      "args": ["windows-mcp", "serve", "--exclude-tools", "PowerShell,Registry,Scrape"]
    }
  }
}
```

Two entries under different names — one read-only for browsing, one with write tools — is a reasonable
pattern. Pin the version for reproducibility: `["windows-mcp@0.8.5", "serve"]`.

## Tool reference (20 tools)

Registered names are PascalCase with no suffix — the tool is `Click`, not `Click-Tool`, even though the
upstream README's prose calls it "Click-Tool". Required parameters are marked.

### Observation

| Tool | Parameters | Notes |
|---|---|---|
| `Screenshot` | `use_annotation=False`, `width_reference_line`, `height_reference_line`, `display` | Fast, visual only. **Does not accept `use_vision` / `use_ui_tree` / `use_dom`.** Best default first call. |
| `Snapshot` | `use_vision=False`, `use_dom=False`, `use_annotation=True`, `use_ui_tree=True`, `width_reference_line`, `height_reference_line`, `display` | Full desktop state: interactive element labels, scrollable regions. `use_dom=True` extracts the DOM of a focused Chrome/Edge/Firefox. |
| `DisplayInventory` | *(none)* | Monitor bounds, resolutions, orientation, DPI scaling. |

### Mouse and keyboard

| Tool | Parameters | Notes |
|---|---|---|
| `Click` | `loc=[x,y]` **or** `label`, `button='left'\|'right'\|'middle'`, `clicks=1` | One of `loc`/`label` is required or it raises. `clicks=0` hovers, `2` double-clicks. |
| `Type` | **`text`** (required), `loc`, `label`, `clear=False`, `caret_position='start'\|'idle'\|'end'`, `press_enter=False` | `text` is positional and required. |
| `Move` | `loc`, `label`, `drag=False`, `from_loc`, `duration` | For a deterministic drag set `from_loc` **and** `drag=True` in one call. |
| `Scroll` | `loc`, `label`, `type='vertical'\|'horizontal'`, `direction='up'\|'down'\|'left'\|'right'`, `wheel_times=1` | The axis parameter is named `type`. |
| `Shortcut` | **`shortcut`** (required) | A single `'+'`-joined string: `"ctrl+c"`, `"win+r"`, `"alt+tab"`. **Not** `keys`. |
| `MultiSelect` | `locs`, `labels`, `press_ctrl=True` | Multi-select items/checkboxes. Default holds Ctrl. |
| `MultiEdit` | `locs=[[x,y,text],...]`, `labels=[[label,text],...]` | Fills several fields in one call. |

### Timing

| Tool | Parameters | Notes |
|---|---|---|
| `Wait` | **`duration`** (int seconds) | **Not** `seconds`. |
| `WaitFor` | `condition`, `text`, `window_name`, `timeout=10.0`, `interval=0.25`, `use_dom` | Polls inside one call — far cheaper than repeated snapshots. Five conditions: `text_exists`, `active_window`, `element_exists`, `element_enabled`, `focused_element`. |

### System

| Tool | Parameters | Notes |
|---|---|---|
| `App` | `mode='launch'\|'launch_executable'\|'resize'\|'switch'`, plus `name`/path, `args`, `cwd`, `window_loc`, `window_size` | `launch` matches Start Menu names, so it depends on display language. |
| `Process` | **`mode='list'\|'kill'`** (required), `sort_by='memory'\|'cpu'\|'name'`, name/pid filters | |
| `PowerShell` | **`command`** (required), `timeout=30` | Arbitrary command execution. |
| `FileSystem` | **`mode`** — `read`, `write`, `copy`, `move`, `delete`, `list`, `search`, `info` | Relative paths resolve against the Desktop. |
| `Registry` | **`mode`** — `get`, `set`, `delete`, `list` | PowerShell path syntax, e.g. `HKCU:\Software\MyApp`. |
| `Clipboard` | **`mode='get'\|'set'`**, `text` | |
| `Scrape` | **`url`** (required), `query`, `use_dom=False`, `use_sampling=True` | Untrusted input — see the injection warning above. |
| `Notification` | `title`, `message`, `app_id` | Native toast. |

### Driving these tools well

1. **Observe before acting.** `Screenshot` when visual context is enough; `Snapshot(use_ui_tree=True)`
   when element labels are needed to click precisely.
2. **Prefer `label` over `loc`.** Labels come from the accessibility tree and survive windows moving,
   resizing, or DPI changes; pixel coordinates do not.
3. **Use `WaitFor`, not `Wait`.** `WaitFor(condition='active_window', window_name='Notepad')` beats a
   fixed sleep and costs far less than polling with snapshots.
4. **Batch form fills** with `MultiEdit` instead of repeated `Type` calls.
5. **`Type` needs `text`.** A call built from the parameter list alone will fail without it.

## Optional: network transport

`serve` also supports SSE and Streamable HTTP, which is what makes remote access possible:

```powershell
uvx windows-mcp serve --transport sse --host localhost --port 8000
uvx windows-mcp serve --transport streamable-http --host localhost --port 8000
```

Generate an auth key (saved to `~/.windows-mcp/config.toml`), optionally with a self-signed cert:

```powershell
uvx windows-mcp auth --transport sse --host 0.0.0.0 --port 8000 --with-tls
```

`uvx windows-mcp install` registers a **scheduled task** that starts a background SSE/HTTP server at every
login (stdio is not supported as a service); `uvx windows-mcp uninstall` removes it.

> **Weigh this carefully.** A network-reachable endpoint with these tools is remote code execution on the
> machine for anyone who reaches it. Never bind `0.0.0.0` on an untrusted network, always set an auth key,
> and prefer `localhost` plus an SSH tunnel or Tailscale over port-forwarding. `--with-tls` generates a
> *self-signed* cert, which encrypts but does not authenticate the server.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Server absent in Claude Desktop, no error | Almost always the MSIX config path. Check `Get-AppxPackage -Name *Claude*` and write to the `LocalCache\Roaming\Claude` path. |
| Absent, and the install is not MSIX | Claude Desktop was not fully quit. Exit from the tray, not just the window. |
| `spawn uvx ENOENT` / `MCP error -32000: Connection closed` | `PATH` not inherited. Use the absolute `%USERPROFILE%\.local\bin\uvx.exe` in `command`. |
| Config silently reverts or servers vanish | A tool wrote the file with a UTF-8 BOM, or a hand edit left trailing commas. Rewrite BOM-free; validate with `Get-Content $f -Raw \| ConvertFrom-Json`. |
| `windows-mcp is now a command group` | Flags were passed before the subcommand. The subcommand comes first: `windows-mcp serve --transport sse`. |
| `App` cannot find an application | Start Menu name matching is language-dependent. Use `mode='launch_executable'` with a full path, or exclude `App`. |
| Nothing happens, or clicks land in the wrong place | The server needs a real interactive desktop session. It cannot drive a locked screen, and an RDP session that has been minimized or disconnected tears down the desktop. |
| Diagnosing further | Claude Desktop logs: `%APPDATA%\Claude\logs\mcp.log` and `mcp-server-windows-mcp.log`. Claude Code: `claude mcp get windows-mcp`. Or run `uvx windows-mcp serve` in a terminal to see startup errors directly. |

## Uninstall

```powershell
claude mcp remove windows-mcp -s user          # Claude Code
uvx windows-mcp uninstall                       # only if the scheduled task was installed
```

For Claude Desktop, delete the `windows-mcp` block from `claude_desktop_config.json` (or restore a
`.bak-*` file) and restart. To drop the cached package entirely: `uv cache clean windows-mcp`.

Remember that uninstalling removes *access*, not exposure. If sensitive credentials were reachable during
a session, rotate them.
