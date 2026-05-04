"use client";
export function GridLayout({ block, children }: any) {
  return <div className="grid w-full h-full content-start gap-4" style={{ gridTemplateColumns: `repeat(auto-fit, minmax(300px, 1fr))` }}>{children}</div>;
}
