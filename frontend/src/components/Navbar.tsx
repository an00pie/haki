"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Shield, 
  LayoutDashboard, 
  Plus, 
  History, 
  Settings, 
  Terminal,
  ArrowUpRight
} from "lucide-react";
import { api } from "@/lib/api";

export default function Navbar() {
  const pathname = usePathname();
  const [healthStatus, setHealthStatus] = useState<"ok" | "checking" | "offline">("checking");

  useEffect(() => {
    let mounted = true;
    api.getHealth()
      .then((data) => {
        if (mounted) setHealthStatus(data.status === "ok" ? "ok" : "offline");
      })
      .catch(() => {
        if (mounted) setHealthStatus("offline");
      });
    return () => { mounted = false; };
  }, []);

  const navLinks = [
    { href: "/dashboard", label: "Dashboard", code: "01" },
    { href: "/investigations/new", label: "New Scan", code: "02" },
    { href: "/history", label: "History", code: "03" },
    { href: "/settings", label: "Settings", code: "04" },
  ];

  return (
    <header className="sticky top-0 z-50 bg-[#080808]/90 backdrop-blur-md border-b border-[#242424]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand: HaKi */}
          <div className="flex items-center space-x-3">
            <Link href="/" className="flex items-center space-x-2.5 group">
              <div className="w-8 h-8 rounded-md bg-[#141414] border border-[#2e2e2e] flex items-center justify-center group-hover:border-[#e5ff00] transition-colors">
                <span className="font-mono font-black text-xs text-[#e5ff00]">HK</span>
              </div>
              <div className="flex items-baseline space-x-1.5">
                <span className="font-extrabold text-lg tracking-tight text-white group-hover:text-neutral-300 transition-colors">
                  HaKi
                </span>
                <span className="text-[10px] font-mono text-neutral-500 uppercase tracking-widest hidden sm:inline">
                  // RISKLOCK
                </span>
              </div>
            </Link>
          </div>

          {/* Navigation Links - Neo-Minimalist Style */}
          <nav className="hidden md:flex items-center space-x-1 font-mono text-xs">
            {navLinks.map((link) => {
              const isActive = pathname === link.href || (link.href !== "/" && pathname.startsWith(link.href));
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-all ${
                    isActive
                      ? "bg-[#181818] text-white border border-[#333333] font-semibold"
                      : "text-neutral-400 hover:text-white hover:bg-[#121212]"
                  }`}
                >
                  <span className="text-neutral-600 text-[10px]">{link.code}</span>
                  <span>{link.label}</span>
                </Link>
              );
            })}
          </nav>

          {/* Status & Neo-Minimalist CTA */}
          <div className="flex items-center space-x-3 font-mono text-xs">
            <div className="hidden sm:flex items-center space-x-2 px-2.5 py-1 rounded-md bg-[#121212] border border-[#242424]">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  healthStatus === "ok"
                    ? "bg-[#e5ff00] animate-pulse"
                    : healthStatus === "checking"
                    ? "bg-amber-400"
                    : "bg-rose-500"
                }`}
              />
              <span className="text-[11px] text-neutral-400 tracking-wider uppercase">
                {healthStatus === "ok" ? "ACTIVE" : healthStatus === "checking" ? "CONNECTING" : "OFFLINE"}
              </span>
            </div>

            <Link
              href="/investigations/new"
              className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-md bg-white hover:bg-neutral-200 text-black font-semibold text-xs transition-transform active:scale-95"
            >
              <span>SCAN</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </div>
    </header>
  );
}
