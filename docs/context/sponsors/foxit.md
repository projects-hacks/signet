# Foxit, "Your Agent Shouldn't Sign That"

| | |
|---|---|
| Prize | 700 USD, second place 300 |
| Contact | theodore_castro@foxitsoftware.come (trailing e is in the source; try .com) |

## The challenge

Build an agent that starts from a plain prompt and ends with a signed document.

Their open source MCP server wraps the Foxit PDF Services API and gives an agent
forty tools for the reversible work: generation, conversion, merging,
compression, OCR, extraction. Signing is left out of the catalogue on purpose.
To send anything for signature the agent must call the Foxit eSign API directly,
with its own credentials, and a person has to sign it.

They say that handoff is the interesting part and they want to see how it is
designed. They also invite disagreement: if signing belongs in the agent's
toolset, or the boundary sits elsewhere, build it that way and defend it.
