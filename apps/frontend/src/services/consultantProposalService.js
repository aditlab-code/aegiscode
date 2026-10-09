/**
 * consultantProposalService.js
 *
 * Logika ekstraksi regex blok proposal task dan ekstraksi blok kode markdown.
 */

export const TASK_FENCE_RE = /```[ \t]*task(?:-proposal)?[ \t]*\r?\n[\s\S]*?```/gi;

export function stripTaskProposal(text) {
  if (!text) return "";
  return String(text).replace(TASK_FENCE_RE, "").replace(/\n{3,}/g, "\n\n").trim();
}

export function assistantText(msg) {
  if (!msg) return "";
  return stripTaskProposal(msg.text || msg.content || "");
}

export function extractFirstCodeBlock(text) {
  if (!text) return "";
  const match = String(text).match(/```(?:[a-zA-Z0-9_+-]+)?\r?\n([\s\S]*?)\r?\n```/);
  return match ? match[1] : "";
}

export function extractTaskProposalText(text) {
  if (!text) return "";
  const match = String(text).match(TASK_FENCE_RE);
  if (!match || !match[0]) return "";
  return match[0].replace(/^```[^\n]*\r?\n/, "").replace(/\r?\n```$/, "").trim();
}
