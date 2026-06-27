"use client";

export default function Overlay({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div className={`overlay-panel${wide ? " wide" : ""}`} onClick={(e) => e.stopPropagation()}>
        <div className="overlay-head">
          <h2 style={{ margin: 0 }}>{title}</h2>
          <button className="close-x" onClick={onClose} aria-label="Close">×</button>
        </div>
        {children}
      </div>
    </div>
  );
}
