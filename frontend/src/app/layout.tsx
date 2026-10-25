import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "HaKi — Autonomous Seller & Storefront Risk Intelligence",
  description: "Deterministic seller risk evaluation, Instagram authenticity signals, media verification, and evidence-backed reporting.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#080808] text-neutral-200 min-h-screen flex flex-col antialiased selection:bg-[#e5ff00] selection:text-black">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
        <footer className="border-t border-[#242424] py-6 text-xs text-neutral-500 font-mono">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center space-x-2">
              <span className="font-bold text-neutral-300">HaKi</span>
              <span>— Local-First Risk Ledger & Auditable Engine</span>
            </div>
            <div className="text-[11px] text-neutral-600 tracking-wider uppercase">
              Deterministic v1.2.0 • Local Gemma AI • Zero Tracking
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
