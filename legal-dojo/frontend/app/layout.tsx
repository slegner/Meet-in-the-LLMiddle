import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Legal Dojo",
  description: "Train against a strategic AI negotiator.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <div className="topbar-inner">
            <Link href="/" className="brand" style={{ textDecoration: "none" }}>
              ⚖ LEGAL DOJO
            </Link>
            <nav className="nav">
              <Link href="/">New Simulation</Link>
              <Link href="/profile">Training Data</Link>
            </nav>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
