import type { ReactNode, SVGProps } from "react";

/** One line-icon set for the app chrome: 20 px box, 2 px round strokes in currentColor. */
function Svg({ children, ...rest }: SVGProps<SVGSVGElement> & { children: ReactNode }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className="icon"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const IconUndo = () => (
  <Svg>
    <path d="M7 4 3 8l4 4" />
    <path d="M3 8h9a5 5 0 0 1 0 10H8" />
  </Svg>
);
export const IconArrowLeft = () => (
  <Svg>
    <path d="M16 10H4M9 5l-5 5 5 5" />
  </Svg>
);
export const IconDownload = () => (
  <Svg>
    <path d="M10 3v10M6 9l4 4 4-4" />
    <path d="M3 15v2h14v-2" />
  </Svg>
);
export const IconUpload = () => (
  <Svg>
    <path d="M10 13V3M6 7l4-4 4 4" />
    <path d="M3 15v2h14v-2" />
  </Svg>
);
export const IconFlag = () => (
  <Svg>
    <path d="M5 18V3" />
    <path d="M5 3h10l-2.5 4L15 11H5" />
  </Svg>
);
/** Settings: three slider rails with knobs. */
export const IconSliders = () => (
  <Svg>
    <path d="M3 5h7M14 5h3M3 10h2M9 10h8M3 15h9M16 15h1" />
    <circle cx="12" cy="5" r="2" />
    <circle cx="7" cy="10" r="2" />
    <circle cx="14" cy="15" r="2" />
  </Svg>
);
export const IconClose = () => (
  <Svg>
    <path d="M5 5l10 10M15 5 5 15" />
  </Svg>
);
export const IconInfo = () => (
  <Svg>
    <circle cx="10" cy="10" r="7.5" />
    <path d="M10 9v5M10 6.2h.01" />
  </Svg>
);
export const IconSkip = () => (
  <Svg>
    <path d="M3 5l6 5-6 5zM10 5l6 5-6 5z" />
    <path d="M18 5v10" />
  </Svg>
);
/** A fir tree: the Lignum mark. */
export const IconTree = (props: SVGProps<SVGSVGElement>) => (
  <Svg {...props}>
    <path d="M10 2 5 8h3l-4 5h12l-4-5h3z" />
    <path d="M10 13v5" />
  </Svg>
);
