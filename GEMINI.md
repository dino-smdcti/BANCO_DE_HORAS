# Gemini CLI Project Directives

## Core Directives
- ALWAYS respect the existing architecture and style.
- ALWAYS perform validation (testing/linting) after changes.
- NEVER introduce secrets into the codebase.

## OS Environment & Command Compatibility
- **Environment**: All commands are executed within a Windows PowerShell environment.
- **Commands**: ALWAYS use PowerShell-compatible syntax. AVOID bash-specific utilities (e.g., `grep`, `sed`, `awk`) unless they are explicitly available in the environment. 
- **Exception**: Only use Linux/bash-style syntax if the user explicitly confirms they are operating in a Linux environment.
