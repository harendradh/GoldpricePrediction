# Prompts

Prompt content lives **inside each Skill module** at `.github/skills/`,
alongside the deterministic fallback. This keeps every skill self-contained
and avoids the prompt-vs-code drift that separate template files create.

To branch a prompt variant: edit the `system_prompt` string inside the
skill module and gate on a parameter. No registry required.
