import { useEffect, useMemo, useState } from "react";
import { statusTone } from "../format";
import { Icon } from "../icons";
import type { Selection, TreeNode } from "../types";

function branchIds(nodes: TreeNode[]): string[] {
  const result: string[] = [];
  const walk = (items: TreeNode[]) => {
    for (const item of items) {
      if (item.children?.length) {
        result.push(item.id);
        walk(item.children);
      }
    }
  };
  walk(nodes);
  return result;
}

function filterNodes(nodes: TreeNode[], query: string): TreeNode[] {
  const needle = query.trim().toLocaleLowerCase("fr");
  if (!needle) return nodes;
  const visit = (node: TreeNode): TreeNode | null => {
    const children = (node.children ?? []).map(visit).filter((item): item is TreeNode => Boolean(item));
    const self = `${node.label} ${node.meta} ${node.id}`.toLocaleLowerCase("fr").includes(needle);
    if (!self && children.length === 0) return null;
    return { ...node, children };
  };
  return nodes.map(visit).filter((item): item is TreeNode => Boolean(item));
}

export function TreeView({
  nodes,
  selection,
  onSelect,
  search,
  emptyMessage,
  ariaLabel,
}: {
  nodes: TreeNode[];
  selection: Selection | null;
  onSelect: (selection: Selection) => void;
  search: string;
  emptyMessage: string;
  ariaLabel: string;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(branchIds(nodes)));
  const filtered = useMemo(() => filterNodes(nodes, search), [nodes, search]);

  useEffect(() => {
    setExpanded(new Set(branchIds(nodes)));
  }, [nodes]);

  const toggle = (id: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const renderNodes = (items: TreeNode[], depth = 0): React.ReactNode =>
    items.map((node) => {
      const isBranch = Boolean(node.children?.length);
      const isOpen = search.trim() ? true : expanded.has(node.id);
      const active = selection?.id === node.id;
      return (
        <li key={`${node.kind}-${node.id}`} role="treeitem" aria-expanded={isBranch ? isOpen : undefined}>
          <div className={`tree-row ${active ? "is-active" : ""}`} style={{ paddingLeft: 6 + depth * 15 }}>
            {isBranch ? (
              <button
                type="button"
                className="tree-toggle"
                onClick={() => toggle(node.id)}
                aria-label={isOpen ? `Replier ${node.label}` : `Déplier ${node.label}`}
              >
                <Icon name={isOpen ? "chevronDown" : "chevron"} size={13} />
              </button>
            ) : (
              <span className="tree-toggle tree-toggle-spacer" />
            )}
            <button
              type="button"
              className="tree-node"
              onClick={() => onSelect({ kind: node.kind, id: node.id } as Selection)}
              data-testid={`tree-${node.kind}-${node.id}`}
            >
              <span className={`tree-icon tree-icon-${node.kind}`}>
                <Icon
                  name={node.kind === "project" ? "projects" : node.kind === "board" ? "tree" : node.kind === "feeder" ? "bolt" : "file"}
                  size={13}
                />
              </span>
              <span className="tree-copy">
                <strong>{node.label}</strong>
                <small>{node.meta}</small>
              </span>
              <span className={`dot dot-${statusTone(node.status)}`} title={node.status} />
            </button>
          </div>
          {isBranch && isOpen && (
            <ul role="group" className="tree-children">
              {renderNodes(node.children ?? [], depth + 1)}
            </ul>
          )}
        </li>
      );
    });

  return (
    <div className="tree-view" data-testid="tree-view">
      <ul role="tree" aria-label={ariaLabel} className="tree-root">
        {filtered.length > 0 ? renderNodes(filtered) : <li className="tree-empty">{emptyMessage}</li>}
      </ul>
    </div>
  );
}
