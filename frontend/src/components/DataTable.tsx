import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Icon } from "../icons";

export type DataColumn<T> = {
  key: string;
  label: string;
  width?: number;
  align?: "left" | "right" | "center";
  sortable?: boolean;
  title?: string;
  render: (row: T) => ReactNode;
};

export type SortState = {
  key: string;
  direction: "asc" | "desc";
};

const ROW_HEIGHT = 36;
const VIRTUALIZE_ABOVE = 200;

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  selectedKey,
  onRowClick,
  sort,
  onSort,
  emptyMessage,
  testId,
  rowTestId,
  rowClassName,
  ariaLabel,
}: {
  columns: Array<DataColumn<T>>;
  rows: T[];
  rowKey: (row: T) => string;
  selectedKey?: string | null;
  onRowClick?: (row: T) => void;
  sort?: SortState | null;
  onSort?: (key: string) => void;
  emptyMessage: string;
  testId?: string;
  rowTestId?: (row: T) => string;
  rowClassName?: (row: T) => string;
  ariaLabel: string;
}) {
  const [widths, setWidths] = useState<Record<string, number>>(() =>
    Object.fromEntries(columns.map((column) => [column.key, column.width ?? 140])),
  );
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(640);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const update = () => setViewportHeight(element.clientHeight || 640);
    update();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(update) : null;
    observer?.observe(element);
    window.addEventListener("resize", update);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", update);
    };
  }, []);

  const virtual = rows.length > VIRTUALIZE_ABOVE;
  const totalHeight = rows.length * ROW_HEIGHT;
  const start = virtual
    ? Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - 8)
    : 0;
  const end = virtual
    ? Math.min(rows.length, start + Math.ceil(viewportHeight / ROW_HEIGHT) + 16)
    : rows.length;
  const visibleRows = useMemo(() => rows.slice(start, end), [rows, start, end]);
  const tableWidth = useMemo(
    () => columns.reduce((sum, column) => sum + (widths[column.key] ?? column.width ?? 140), 0),
    [columns, widths],
  );

  const beginResize = (event: React.PointerEvent, key: string) => {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startWidth = widths[key] ?? 140;
    const move = (moveEvent: PointerEvent) => {
      const next = Math.max(72, Math.min(420, startWidth + moveEvent.clientX - startX));
      setWidths((current) => ({ ...current, [key]: next }));
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  return (
    <div
      className="grid-scroll"
      ref={containerRef}
      onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
      data-testid={testId}
      role="region"
      aria-label={`${ariaLabel} — zone défilante`}
      tabIndex={0}
    >
      <table
        className="grid-table"
        aria-label={ariaLabel}
        style={{ minWidth: Math.max(560, tableWidth), tableLayout: "fixed" }}
      >
        <colgroup>
          {columns.map((column) => (
            <col key={column.key} style={{ width: widths[column.key] ?? column.width ?? 140 }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {columns.map((column) => {
              const isSorted = sort?.key === column.key;
              return (
                <th
                  key={column.key}
                  className={`align-${column.align ?? "left"} ${isSorted ? "is-sorted" : ""}`}
                  aria-sort={
                    isSorted ? (sort?.direction === "asc" ? "ascending" : "descending") : undefined
                  }
                  title={column.title}
                >
                  {column.sortable && onSort ? (
                    <button
                      type="button"
                      className="table-sort"
                      onClick={() => onSort(column.key)}
                      data-testid={`sort-${column.key}`}
                    >
                      {column.label}
                      <span className={`sort-mark ${isSorted ? "is-visible" : ""}`}>
                        {isSorted && sort?.direction === "desc" ? "↓" : "↑"}
                      </span>
                    </button>
                  ) : (
                    column.label
                  )}
                  <span
                    className="column-resizer"
                    onPointerDown={(event) => beginResize(event, column.key)}
                    aria-hidden="true"
                  />
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {virtual && start > 0 && (
            <tr className="virtual-spacer" aria-hidden="true">
              <td colSpan={columns.length} style={{ height: start * ROW_HEIGHT }} />
            </tr>
          )}
          {visibleRows.map((row) => {
            const key = rowKey(row);
            const selected = selectedKey === key;
            return (
              <tr
                key={key}
                className={`${selected ? "is-selected" : ""} ${rowClassName?.(row) ?? ""}`}
                tabIndex={0}
                aria-selected={selected}
                data-testid={rowTestId?.(row)}
                onClick={() => onRowClick?.(row)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onRowClick?.(row);
                  }
                }}
              >
                {columns.map((column) => (
                  <td key={column.key} className={`align-${column.align ?? "left"}`}>
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="table-empty">
                {emptyMessage}
              </td>
            </tr>
          )}
          {virtual && end < rows.length && (
            <tr className="virtual-spacer" aria-hidden="true">
              <td colSpan={columns.length} style={{ height: (rows.length - end) * ROW_HEIGHT }} />
            </tr>
          )}
        </tbody>
      </table>
      {virtual && (
        <div className="virtual-note" aria-hidden="true">
          <Icon name="performance" size={12} />
          Virtualisation active · {rows.length} lignes · hauteur {Math.round(totalHeight)} px
        </div>
      )}
    </div>
  );
}

