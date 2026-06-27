import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import GuideButton from "./components/GuideButton";

export const metadata: Metadata = {
  title: "Meet in the LLMiddle",
  description: "Train against a strategic AI negotiator.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <div className="topbar-inner">
            <Link href="/" className="brand" style={{ textDecoration: "none" }}>
              ⚖ LLMIDDLE
            </Link>
            <nav className="nav">
              <Link href="/">New Simulation</Link>
              <Link href="/profile">Training Data</Link>
            </nav>
          </div>
        </header>
        {children}
        <GuideButton />
      </body>
    </html>
  );
}
