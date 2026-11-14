type IconName =
  | "dashboard"
  | "projects"
  | "balance"
  | "engine"
  | "architecture"
  | "library"
  | "report"
  | "settings"
  | "performance"
  | "search"
  | "chevron"
  | "chevronDown"
  | "offline"
  | "shield"
  | "sun"
  | "moon"
  | "bolt"
  | "tree"
  | "file"
  | "arrow"
  | "check"
  | "alert"
  | "close"
  | "edit"
  | "reset"
  | "filter"
  | "info"
  | "lock"
  | "cpu"
  | "chart"
  | "activity"
  | "download";

const paths: Record<IconName, React.ReactNode> = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </>
  ),
  projects: (
    <>
      <path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H10l2 2h6.5A2.5 2.5 0 0 1 21 9.5v8A2.5 2.5 0 0 1 18.5 20h-13A2.5 2.5 0 0 1 3 17.5v-10Z" />
      <path d="M3 10h18" />
    </>
  ),
  balance: (
    <>
      <path d="M4 6h16M4 12h16M4 18h16" />
      <path d="M8 4v4M16 10v4M10 16v4" />
    </>
  ),
  engine: (
    <>
      <path d="M9 3h6M10 3v3h4V3M7 9h10l2 4v6H5v-6l2-4Z" />
      <path d="M9 14h6M9 17h3" />
    </>
  ),
  architecture: (
    <>
      <rect x="3" y="4" width="7" height="6" rx="1.5" />
      <rect x="14" y="14" width="7" height="6" rx="1.5" />
      <rect x="3" y="14" width="7" height="6" rx="1.5" />
      <path d="M6.5 10v4M17.5 14v-4H6.5" />
    </>
  ),
  library: (
    <>
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H19v16H6.5A2.5 2.5 0 0 0 4 21.5V5.5Z" />
      <path d="M4 18.5A2.5 2.5 0 0 1 6.5 16H19" />
    </>
  ),
  report: (
    <>
      <path d="M6 3h8l4 4v14H6V3Z" />
      <path d="M14 3v5h5M9 12h6M9 16h6" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" />
    </>
  ),
  performance: (
    <>
      <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />
      <path d="m4 7 6-3 6 5 5-4" />
    </>
  ),
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m16 16 4.5 4.5" />
    </>
  ),
  chevron: <path d="m9 6 6 6-6 6" />,
  chevronDown: <path d="m6 9 6 6 6-6" />,
  offline: (
    <>
      <path d="M5 12.5a7 7 0 0 1 11-5.7M19 11.5a7 7 0 0 1-11 5.7" />
      <path d="M8.5 15.5a5 5 0 0 1 7 0M11 18.5a2 2 0 0 1 2 0M3 3l18 18" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3 20 6v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3Z" />
      <path d="m8.5 12 2.5 2.5 4.5-5" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>
  ),
  moon: <path d="M20 15.5A8.5 8.5 0 0 1 8.5 4 8.5 8.5 0 1 0 20 15.5Z" />,
  bolt: <path d="m13 2-8 12h6l-1 8 8-12h-6l1-8Z" />,
  tree: (
    <>
      <path d="M5 4v16M5 8h6M5 14h6M5 20h6" />
      <rect x="11" y="5" width="8" height="6" rx="1.5" />
      <rect x="11" y="17" width="8" height="6" rx="1.5" />
    </>
  ),
  file: (
    <>
      <path d="M6 3h8l4 4v14H6V3Z" />
      <path d="M14 3v5h5" />
    </>
  ),
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  check: <path d="m5 12 4 4L19 6" />,
  alert: (
    <>
      <path d="M12 3 22 21H2L12 3Z" />
      <path d="M12 9v5M12 17h.01" />
    </>
  ),
  close: <path d="M6 6l12 12M18 6 6 18" />,
  edit: (
    <>
      <path d="m4 20 4.5-1 10-10-3.5-3.5-10 10L4 20Z" />
      <path d="m13.5 6.5 3.5 3.5" />
    </>
  ),
  reset: (
    <>
      <path d="M4 9V4h5M20 15v5h-5" />
      <path d="M5.5 5.5A8 8 0 0 1 20 12M18.5 18.5A8 8 0 0 1 4 12" />
    </>
  ),
  filter: <path d="M3 5h18l-7 8v6l-4 2v-8L3 5Z" />,
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </>
  ),
  lock: (
    <>
      <rect x="5" y="10" width="14" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </>
  ),
  cpu: (
    <>
      <rect x="7" y="7" width="10" height="10" rx="2" />
      <path d="M9 3v4M15 3v4M9 17v4M15 17v4M3 9h4M3 15h4M17 9h4M17 15h4" />
    </>
  ),
  chart: (
    <>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
      <path d="M4 9 10 4l6 7 5-4" />
    </>
  ),
  activity: <path d="M3 12h4l2.5-6 5 12 2.5-6h4" />,
  download: (
    <>
      <path d="M12 3v12M7 10l5 5 5-5" />
      <path d="M4 19h16" />
    </>
  ),
};

export function Icon({
  name,
  size = 18,
  className,
}: {
  name: IconName;
  size?: number;
  className?: string;
}) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

export type { IconName };
