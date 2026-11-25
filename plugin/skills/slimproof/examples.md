# Examples

Real rewrites from an Obsidian MCP server (`~` = estimate at 4 characters per token).

## 1. Tutorial → essentials (SP006): `search_query`, ~462 → ~143 tokens
Before: one sentence of purpose, then a full example note, a list of 7 JsonLogic operators, 2 extra operators, the return shape and 5 examples.

After:
> Find notes by metadata with a JsonLogic query, evaluated per note against {path, content, tags, frontmatter, stat {ctime, mtime, size}, links, backlinks, unresolvedLinks}. Returns [{filename, result}] for notes where the result is truthy. Nested fields: {"var": "frontmatter.status"}. Supports standard JsonLogic plus {"glob": [pattern, value]} and {"regexp": [pattern, value]}. Example: {"and": [{"in": ["work", {"var": "tags"}]}, {"==": [{"var": "frontmatter.status"}, "done"]}]}. To see a real note's shape and frontmatter fields, vault_read any file without targeting.

Kept: the note shape (the model needs it to write queries), the non-standard operators, one example, the pointer to vault_read. Cut: standard operators the model already knows.

## 2. Nested parameter (SP007): `vault_patch` → `content`, ~179 → ~77 tokens
Before:
> String payload: a heading/block body or label, a new block id for a block `marker` rename (letters, numbers, hyphens, and underscores only), or a new frontmatter key name for a frontmatter `marker` rename. Heading levels are relative to the edited span (a leading `#` becomes a direct child). For heading writes, whitespace is library-owned: leading/trailing blank lines here are ignored, and the engine supplies the blank line that keeps inserted content a separate block — never add newlines to control spacing. (Block-target `content` is the exception: it is spliced literally for inline edits.) A heading `marker` rename may not contain a line break. Provide exactly one of `content`, `value`, or `destination`.

After:
> Text payload: a body or label, or for a marker rename the new block id (letters, numbers, - and _ only) or frontmatter key. For heading writes, blank lines are handled for you; don't add newlines for spacing. Block-target content is spliced literally. A heading marker rename may not contain a line break.

"Provide exactly one of…" was repeated in 3 parameters, so it moved once to the tool description. "Heading levels are relative" moved there too. Every constraint stayed, including the allowed characters for the block id.

## 3. Don't: invent or drop facts
A rewrite of `vault_patch` said "get … the version token from vault_get_document_map". The original never says that. Another dropped the allowed block-id characters. Both passed `compare`, because the guard checks structure, not meaning. Re-read each rewrite against the original before calling `compare`.