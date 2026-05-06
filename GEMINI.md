# Gemini CLI Project Directives

## Core Directives
- ALWAYS respect the existing architecture and style.
- ALWAYS perform validation (testing/linting) after changes.
- NEVER introduce secrets into the codebase.

## Shell Command Security & Best Practices
- **NEVER use "&&"**: You are strictly prohibited from using the "&&" operator for chaining shell commands. This operator is not reliable in all Windows environments and has caused repeated execution failures.
- **Always use ";"**: Always use the semicolon (";") operator to chain shell commands (e.g., `git add . ; git commit -m "msg" ; git push origin main`). It is the consistent and reliable separator for your operational environment.
