/**
 * Resolve display name for a project entity.
 * @param {object} [project]
 * @returns {string}
 */
export function getProjectDisplayName(project) {
  return project?.name || project?.title || "Untitled Project";
}

/**
 * Format and truncate project path responsively according to breakpoint tiers and maxChars.
 * @param {string} path
 * @param {{ maxChars?: number, tier?: 'desktop' | 'compact' | 'mobile' }} [options]
 * @returns {string}
 */
export function truncateProjectPath(
  path,
  { maxChars = 40, tier = "desktop" } = {}
) {
  if (!path) return "";
  const normalized = String(path).replace(/\\/g, "/").replace(/\/+$/, "");
  if (!normalized) return "/";

  // Compact and Mobile tiers display only the folder basename
  if (tier === "compact" || tier === "mobile") {
    const parts = normalized.split("/").filter(Boolean);
    return parts[parts.length - 1] || normalized;
  }

  // Replace standard Unix/macOS home directory prefixes with ~
  const homeReplaced = normalized.replace(/^\/(?:Users|home)\/[^/]+/, "~");

  if (homeReplaced.length <= maxChars) {
    return homeReplaced;
  }

  const segments = homeReplaced.split("/").filter(Boolean);
  const basename = segments.pop() || "";
  let head = homeReplaced.startsWith("/")
    ? `/${segments[0] || ""}`
    : segments[0] || "";
  if (homeReplaced.startsWith("~")) {
    head = "~";
  }

  const candidate = `${head}/.../${basename}`;
  if (candidate.length <= maxChars) {
    return candidate;
  }

  if (basename.length + 4 <= maxChars) {
    return `.../${basename}`;
  }

  return basename.length > maxChars
    ? `${basename.slice(0, Math.max(1, maxChars - 3))}...`
    : basename;
}

/**
 * Format project object for select / dropdown options.
 * @param {object} project
 * @returns {{ value: string|number|undefined, label: string, path: string|undefined }}
 */
export function formatProjectOption(project) {
  return {
    value: project?.id,
    label: getProjectDisplayName(project),
    path: project?.path,
  };
}

/**
 * Sort project list with active project first, then remaining alphabetically by name.
 * @param {Array<object>} projects
 * @param {string|number|null} [activeId=null]
 * @returns {Array<object>}
 */
export function sortProjects(projects = [], activeId = null) {
  if (!Array.isArray(projects)) return [];
  const copy = [...projects];
  return copy.sort((a, b) => {
    const aActive = activeId != null && a?.id === activeId;
    const bActive = activeId != null && b?.id === activeId;
    if (aActive && !bActive) return -1;
    if (!aActive && bActive) return 1;
    const nameA = String(getProjectDisplayName(a)).toLowerCase();
    const nameB = String(getProjectDisplayName(b)).toLowerCase();
    return nameA.localeCompare(nameB);
  });
}
