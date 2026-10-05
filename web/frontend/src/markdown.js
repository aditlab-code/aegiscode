// Markdown-lite renderer (self-contained, tanpa dependency baru).
//
// Dipakai bersama oleh ReportViewer (Agent Report) dan ConsultantChat
// (jawaban Consultant) sehingga tidak ada renderer duplikat. Mendukung:
// heading, paragraf, list (bullet/number), code block, blockquote, hr, dan
// inline (`code`, **bold**, *italic*).
//
// Keamanan: konten di-escape lebih dulu, lalu hanya markup terbatas yang
// dihasilkan. TIDAK menerima HTML mentah dari sumber.

export function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Inline Markdown: `code`, **bold**, *italic*, [link](url).
export function inlineMarkdown(text) {
  let out = escapeHtml(text);
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, label, href) => {
    const rawUrl = href.trim().replace(/&amp;/g, "&");
    if (/^(https?:\/\/|mailto:|#|\/)/i.test(rawUrl)) {
      const isExternal = /^https?:\/\//i.test(rawUrl);
      const targetRel = isExternal ? ' target="_blank" rel="noopener noreferrer"' : '';
      return `<a class="md-link" href="${escapeHtml(rawUrl)}"${targetRel}>${label}</a>`;
    }
    return match;
  });
  return out;
}

// Helper untuk parsing tabel GFM
function parseTableRow(line) {
  let trimmed = line.trim();
  if (trimmed.startsWith("|")) trimmed = trimmed.slice(1);
  if (trimmed.endsWith("|")) trimmed = trimmed.slice(0, -1);
  return trimmed.split("|").map((cell) => cell.trim());
}

function parseTableSeparator(line) {
  if (!line || !line.includes("-")) return null;
  const cells = parseTableRow(line);
  if (!cells.length) return null;
  const aligns = [];
  for (const c of cells) {
    if (!/^:?-{1,}:?$/.test(c)) return null;
    const left = c.startsWith(":");
    const right = c.endsWith(":");
    if (left && right) aligns.push("center");
    else if (right) aligns.push("right");
    else if (left) aligns.push("left");
    else aligns.push(null);
  }
  return aligns;
}

// Markdown-lite -> HTML (deterministik, tanpa dependency).
export function renderMarkdown(md) {
  if (md == null) return "";
  const lines = String(md).replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let inCode = false;
  let codeBuf = [];
  let codeLang = "";
  let listType = null;
  let para = [];

  const flushPara = () => {
    if (para.length) {
      out.push(`<p>${inlineMarkdown(para.join(" "))}</p>`);
      para = [];
    }
  };
  const closeList = () => {
    if (listType) {
      out.push(`</${listType}>`);
      listType = null;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.trim().startsWith("```")) {
      if (inCode) {
        const langAttr = codeLang ? ` data-lang="${escapeHtml(codeLang)}"` : "";
        out.push(`<pre class="md-code"${langAttr}><code>${escapeHtml(codeBuf.join("\n"))}</code></pre>`);
        codeBuf = [];
        codeLang = "";
        inCode = false;
      } else {
        flushPara();
        closeList();
        const m = line.trim().match(/^```([a-zA-Z0-9_.-]+)/);
        codeLang = m ? m[1] : "";
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      codeBuf.push(line);
      continue;
    }
    if (!line.trim()) {
      flushPara();
      closeList();
      continue;
    }

    // GFM Table detection: line memiliki | dan baris berikutnya adalah separator (|---|)
    if (line.includes("|") && i + 1 < lines.length) {
      const aligns = parseTableSeparator(lines[i + 1]);
      if (aligns) {
        flushPara();
        closeList();
        const headers = parseTableRow(line);
        const rows = [];
        i += 2;
        while (i < lines.length) {
          const nextLine = lines[i];
          if (
            !nextLine.trim() ||
            !nextLine.includes("|") ||
            nextLine.trim().startsWith("```") ||
            /^\s*#{1,6}\s+/.test(nextLine)
          ) {
            i--; // Kembalikan pointer agar diproses loop utama
            break;
          }
          rows.push(parseTableRow(nextLine));
          i++;
        }

        const tableHtml = [];
        tableHtml.push('<div class="md-table-wrap"><table class="md-table">');
        tableHtml.push("<thead><tr>");
        for (let c = 0; c < headers.length; c++) {
          const align = aligns[c] ? ` align="${aligns[c]}"` : "";
          tableHtml.push(`<th${align}>${inlineMarkdown(headers[c] || "")}</th>`);
        }
        tableHtml.push("</tr></thead>");

        if (rows.length) {
          tableHtml.push("<tbody>");
          for (const row of rows) {
            tableHtml.push("<tr>");
            for (let c = 0; c < headers.length; c++) {
              const align = aligns[c] ? ` align="${aligns[c]}"` : "";
              tableHtml.push(`<td${align}>${inlineMarkdown(row[c] || "")}</td>`);
            }
            tableHtml.push("</tr>");
          }
          tableHtml.push("</tbody>");
        }
        tableHtml.push("</table></div>");
        out.push(tableHtml.join(""));
        continue;
      }
    }

    let m;
    if ((m = line.match(/^(#{1,6})\s+(.*)$/))) {
      flushPara();
      closeList();
      const level = m[1].length;
      out.push(`<h${level} class="md-h">${inlineMarkdown(m[2])}</h${level}>`);
      continue;
    }
    if (/^\s*(---|\*\*\*|___)\s*$/.test(line)) {
      flushPara();
      closeList();
      out.push('<hr class="md-hr" />');
      continue;
    }
    if ((m = line.match(/^\s*[-*+]\s+(.*)$/))) {
      flushPara();
      if (listType !== "ul") {
        closeList();
        out.push('<ul class="md-ul">');
        listType = "ul";
      }
      const itemText = m[1];
      const taskMatch = itemText.match(/^\[([ xX])\]\s*(.*)$/);
      if (taskMatch) {
        const checked = taskMatch[1].toLowerCase() === "x";
        const checkedAttr = checked ? ' checked=""' : "";
        out.push(
          `<li class="md-task-item"><input type="checkbox" disabled=""${checkedAttr}/> <span>${inlineMarkdown(
            taskMatch[2]
          )}</span></li>`
        );
      } else {
        out.push(`<li>${inlineMarkdown(itemText)}</li>`);
      }
      continue;
    }
    if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))) {
      flushPara();
      if (listType !== "ol") {
        closeList();
        out.push('<ol class="md-ol">');
        listType = "ol";
      }
      const itemText = m[1];
      const taskMatch = itemText.match(/^\[([ xX])\]\s*(.*)$/);
      if (taskMatch) {
        const checked = taskMatch[1].toLowerCase() === "x";
        const checkedAttr = checked ? ' checked=""' : "";
        out.push(
          `<li class="md-task-item"><input type="checkbox" disabled=""${checkedAttr}/> <span>${inlineMarkdown(
            taskMatch[2]
          )}</span></li>`
        );
      } else {
        out.push(`<li>${inlineMarkdown(itemText)}</li>`);
      }
      continue;
    }
    if ((m = line.match(/^\s*>\s?(.*)$/))) {
      flushPara();
      closeList();
      out.push(`<blockquote class="md-quote">${inlineMarkdown(m[1])}</blockquote>`);
      continue;
    }
    para.push(line.trim());
  }

  if (inCode) {
    const langAttr = codeLang ? ` data-lang="${escapeHtml(codeLang)}"` : "";
    out.push(`<pre class="md-code"${langAttr}><code>${escapeHtml(codeBuf.join("\n"))}</code></pre>`);
  }
  flushPara();
  closeList();
  return out.join("\n");
}
