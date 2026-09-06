"""The shell: what bolts graphy onto a repo an agent works in. Three hooks and one gate, stdlib
Python and bash, the contract exit codes and stdout — usable from Claude Code (the reference
harness, `claude/settings.json`) or from any agent that can run a shell command and read a file
(`hooks/*.sh`, the same entry points). `graphy shell install --repo <abs>` writes them into an
eaten repo with every path declared, never guessed."""
