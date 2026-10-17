import type { SVGProps } from "react";

/** App mark: a building volume in isometric view, its floors drawn on one face. */
export function BrandMark(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path
        d="M12 2.5 20 7l-8 4.5L4 7z"
        fill="currentColor"
        fillOpacity={0.18}
      />
      <path d="M4 7v10l8 4.5 8-4.5V7" />
      <path d="M12 11.5v10" />
      <path d="m4 10.3 8 4.5m-8-1.2 8 4.5" />
    </svg>
  );
}
