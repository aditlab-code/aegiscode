import assert from "node:assert/strict";
import { escapeHtml, inlineMarkdown, renderMarkdown } from "./markdown.js";

// --- 1. Basic HTML Escaping ---
assert.equal(escapeHtml('<script>alert("xss")</script>'), "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;".replace(/&quot;/g, '"'));
assert.equal(escapeHtml("Foo & Bar"), "Foo &amp; Bar");

// --- 2. Inline Markdown: bold, italic, code, links ---
{
  const html = inlineMarkdown("This is **bold** and *italic* and `code`.");
  assert.ok(html.includes("<strong>bold</strong>"));
  assert.ok(html.includes("<em>italic</em>"));
  assert.ok(html.includes("<code>code</code>"));
}

// Safe links
{
  const link = inlineMarkdown("[Docs](https://aegis.dev/guide)");
  assert.ok(link.includes('<a class="md-link" href="https://aegis.dev/guide" target="_blank" rel="noopener noreferrer">Docs</a>'));

  const anchor = inlineMarkdown("[Section](#setup)");
  assert.ok(anchor.includes('<a class="md-link" href="#setup">Section</a>'));
  assert.ok(!anchor.includes('target="_blank"')); // internal anchor should not open in new tab

  // Malicious javascript link should NOT be converted to clickable <a>
  const unsafe = inlineMarkdown("[Click](javascript:alert(1))");
  assert.ok(!unsafe.includes("<a"));
  assert.ok(unsafe.includes("[Click](javascript:alert(1))"));
}

// --- 3. Headings, Paragraphs, Quotes, HR ---
{
  const md = `# Title\n## Subtitle\n\nParagraph text here.\n\n> A quote\n\n---`;
  const html = renderMarkdown(md);
  assert.ok(html.includes('<h1 class="md-h">Title</h1>'));
  assert.ok(html.includes('<h2 class="md-h">Subtitle</h2>'));
  assert.ok(html.includes('<p>Paragraph text here.</p>'));
  assert.ok(html.includes('<blockquote class="md-quote">A quote</blockquote>'));
  assert.ok(html.includes('<hr class="md-hr" />'));
}

// --- 4. Code Blocks with and without language tags ---
{
  const codeWithLang = "```python\ndef hello():\n    print('world')\n```";
  const html = renderMarkdown(codeWithLang);
  assert.ok(html.includes('<pre class="md-code" data-lang="python"><code>def hello():\n    print(\'world\')</code></pre>'));

  const codeWithoutLang = "```\nplain text code\n```";
  const htmlPlain = renderMarkdown(codeWithoutLang);
  assert.ok(htmlPlain.includes('<pre class="md-code"><code>plain text code</code></pre>'));
  assert.ok(!htmlPlain.includes('data-lang'));
}

// --- 5. Task Lists / Checklists ---
{
  const taskMd = `- [ ] Task todo\n- [x] Task done\n- Regular bullet`;
  const html = renderMarkdown(taskMd);
  assert.ok(html.includes('<ul class="md-ul">'));
  assert.ok(html.includes('<li class="md-task-item"><input type="checkbox" disabled=""/> <span>Task todo</span></li>'));
  assert.ok(html.includes('<li class="md-task-item"><input type="checkbox" disabled="" checked=""/> <span>Task done</span></li>'));
  assert.ok(html.includes('<li>Regular bullet</li>'));
}

// --- 6. GFM Tables ---
{
  const tableMd = `
| Item | Status | Priority |
| :--- | :---: | ---: |
| Feature A | In Progress | High |
| Bug B | Resolved | Low |
`;
  const html = renderMarkdown(tableMd);
  assert.ok(html.includes('<div class="md-table-wrap"><table class="md-table">'));
  assert.ok(html.includes('<thead><tr><th align="left">Item</th><th align="center">Status</th><th align="right">Priority</th></tr></thead>'));
  assert.ok(html.includes('<tbody>'));
  assert.ok(html.includes('<tr><td align="left">Feature A</td><td align="center">In Progress</td><td align="right">High</td></tr>'));
  assert.ok(html.includes('<tr><td align="left">Bug B</td><td align="center">Resolved</td><td align="right">Low</td></tr>'));
  assert.ok(html.includes('</tbody></table></div>'));
}

// --- 7. Table followed by Paragraph and Code Block ---
{
  const mixedMd = `
Summary of findings:

| Metric | Value |
|---|---|
| Total | 42 |

\`\`\`json
{"total": 42}
\`\`\`
`;
  const html = renderMarkdown(mixedMd);
  assert.ok(html.includes('<p>Summary of findings:</p>'));
  assert.ok(html.includes('<table class="md-table">'));
  assert.ok(html.includes('<th>Metric</th><th>Value</th>'));
  assert.ok(html.includes('<td>Total</td><td>42</td>'));
  assert.ok(html.includes('<pre class="md-code" data-lang="json">'));
}

console.log("[PASS] All markdown.test.mjs assertions passed cleanly.");
