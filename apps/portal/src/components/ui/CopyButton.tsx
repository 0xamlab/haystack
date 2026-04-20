"use client";
import { useState } from "react";

/** Copy-to-clipboard button that shows "Copied!" for 2 s. */
export function CopyButton({
  text,
  style,
}: {
  text: string;
  style?: React.CSSProperties;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="ag-button ag-button--sm"
      style={{ opacity: 0.85, ...style }}
      onClick={() => {
        navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        });
      }}
    >
      <i
        className={`fa-solid ${copied ? "fa-check" : "fa-copy"}`}
        style={{ marginRight: 4 }}
      />
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}
