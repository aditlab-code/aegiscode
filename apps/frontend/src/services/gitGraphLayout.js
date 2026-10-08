/**
 * Pure zero-dependency layout engine for rendering Git commit railway graphs in SVG.
 * Computes lanes, branch tracks, merge curves, and commit node coordinates.
 */

export const GRAPH_PALETTE = [
  "#a855f7", // Purple (Primary / main)
  "#38bdf8", // Sky Blue
  "#10f09a", // Mint Emerald
  "#f59e0b", // Amber
  "#ec4899", // Pink
  "#6366f1", // Indigo
  "#14b8a6", // Teal
  "#f97316", // Orange
];

/**
 * Parse Git ref decoration string (e.g. "HEAD -> main, origin/main, tag: v1.0.0")
 * into structured badge descriptors.
 *
 * @param {Array<string>|string} refsRaw
 * @returns {Array<{ type: string, name: string, label: string }>}
 */
export function parseGitRefs(refsRaw) {
  if (!refsRaw) return [];
  const list = Array.isArray(refsRaw)
    ? refsRaw
    : String(refsRaw)
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

  const parsed = [];
  for (const item of list) {
    const raw = String(item).trim();
    if (!raw) continue;

    if (raw.startsWith("HEAD -> ")) {
      const branchName = raw.replace("HEAD -> ", "").trim();
      parsed.push({ type: "head", name: "HEAD", label: "HEAD" });
      parsed.push({ type: "branch", name: branchName, label: branchName });
    } else if (raw === "HEAD") {
      parsed.push({ type: "head", name: "HEAD", label: "HEAD" });
    } else if (raw.startsWith("tag: ")) {
      const tagName = raw.replace("tag: ", "").trim();
      parsed.push({ type: "tag", name: tagName, label: tagName });
    } else if (raw.includes("/")) {
      parsed.push({ type: "remote", name: raw, label: raw });
    } else {
      parsed.push({ type: "branch", name: raw, label: raw });
    }
  }

  // Deduplicate by name and type
  const seen = new Set();
  return parsed.filter((r) => {
    const key = `${r.type}:${r.name}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/**
 * Assign lanes and compute SVG line segments for a list of Git commits.
 * Commits are expected in topological order (newest first).
 *
 * @param {Array<Object>} commits - List of commits with { hash, parents, ... }
 * @param {Object} options - Configuration: { laneWidth, rowHeight, nodeRadius }
 * @returns {Array<Object>} Enriched commits with { lane, color, cx, cy, tracks, refs }
 */
export function computeGitGraph(commits = [], options = {}) {
  const laneWidth = options.laneWidth || 16;
  const rowHeight = options.rowHeight || 44;
  const nodeRadius = options.nodeRadius || 4.5;
  const xOffset = options.xOffset || 12;

  if (!Array.isArray(commits) || commits.length === 0) {
    return [];
  }

  // Active lanes array holding the commit hash that next expects to occupy that lane
  let activeLanes = [];
  let maxLanesUsed = 1;

  const result = [];

  for (let i = 0; i < commits.length; i++) {
    const commit = commits[i];
    const hash = commit.hash || commit.short_hash || `c_${i}`;
    const parents = Array.isArray(commit.parents) ? commit.parents : [];

    // 1. Determine lane for current commit
    let lane = activeLanes.indexOf(hash);
    if (lane === -1) {
      // Find first empty lane or push new lane
      lane = activeLanes.indexOf(null);
      if (lane === -1) {
        lane = activeLanes.length;
        activeLanes.push(hash);
      } else {
        activeLanes[lane] = hash;
      }
    }

    if (activeLanes.length > maxLanesUsed) {
      maxLanesUsed = activeLanes.length;
    }

    const color = GRAPH_PALETTE[lane % GRAPH_PALETTE.length];
    const cx = xOffset + lane * laneWidth;
    const cy = rowHeight / 2;

    // Snapshot lanes before mutating for parents
    const lanesBefore = [...activeLanes];

    // 2. Prepare next lane states for parents
    if (parents.length === 0) {
      // Root commit - frees its lane
      activeLanes[lane] = null;
    } else {
      // Primary parent inherits this lane
      activeLanes[lane] = parents[0];

      // Secondary parents (merge commit) need their lanes
      for (let pIdx = 1; pIdx < parents.length; pIdx++) {
        const parentHash = parents[pIdx];
        if (!activeLanes.includes(parentHash)) {
          const emptySlot = activeLanes.indexOf(null);
          if (emptySlot === -1) {
            activeLanes.push(parentHash);
          } else {
            activeLanes[emptySlot] = parentHash;
          }
        }
      }
    }

    // Trim trailing nulls from activeLanes
    while (activeLanes.length > 0 && activeLanes[activeLanes.length - 1] === null) {
      activeLanes.pop();
    }

    const lanesAfter = [...activeLanes];

    // 3. Compute SVG track paths for this commit row
    const tracks = [];

    // Tracks that continue passing through this row vertically
    for (let l = 0; l < Math.max(lanesBefore.length, lanesAfter.length); l++) {
      if (l === lane) continue;
      const continuesBefore = lanesBefore[l] !== null && lanesBefore[l] !== undefined;
      const continuesAfter = lanesAfter[l] !== null && lanesAfter[l] !== undefined;

      if (continuesBefore && continuesAfter) {
        const lx = xOffset + l * laneWidth;
        tracks.push({
          type: "vertical",
          d: `M ${lx} 0 L ${lx} ${rowHeight}`,
          color: GRAPH_PALETTE[l % GRAPH_PALETTE.length],
        });
      }
    }

    // Upper vertical line (from top of row down to commit node) if this lane existed above
    if (lanesBefore[lane] !== null && lanesBefore[lane] !== undefined) {
      tracks.push({
        type: "top-in",
        d: `M ${cx} 0 L ${cx} ${cy}`,
        color,
      });
    }

    // Lower connection(s) to parents
    if (parents.length > 0) {
      // Connection to primary parent (at same lane)
      tracks.push({
        type: "bottom-out",
        d: `M ${cx} ${cy} L ${cx} ${rowHeight}`,
        color,
      });

      // Connections to merged parents (if lane differs)
      for (let pIdx = 1; pIdx < parents.length; pIdx++) {
        const parentHash = parents[pIdx];
        const targetLane = lanesAfter.indexOf(parentHash);
        if (targetLane !== -1 && targetLane !== lane) {
          const targetX = xOffset + targetLane * laneWidth;
          const targetColor = GRAPH_PALETTE[targetLane % GRAPH_PALETTE.length];
          // Smooth bezier curve branching/merging from node to parent lane
          const d = `M ${cx} ${cy} C ${cx} ${rowHeight * 0.75}, ${targetX} ${rowHeight * 0.25}, ${targetX} ${rowHeight}`;
          tracks.push({
            type: "merge",
            d,
            color: targetColor,
          });
        }
      }
    }

    // Parsed ref badges
    const parsedRefs = parseGitRefs(commit.refs);

    result.push({
      ...commit,
      lane,
      color,
      cx,
      cy,
      r: nodeRadius,
      tracks,
      parsedRefs,
    });
  }

  // Calculate overall graph width needed
  const totalWidth = Math.max(32, xOffset * 2 + (maxLanesUsed - 1) * laneWidth);

  return result.map((c) => ({
    ...c,
    graphWidth: totalWidth,
    rowHeight,
  }));
}
