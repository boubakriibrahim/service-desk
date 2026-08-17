"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CheckSquare2, ChevronDown, Database, LogOut, Search, Settings, Wrench } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";

const nav = [
  { href: "/work", label: "Work", icon: Search },
  { href: "/sources", label: "Sources", icon: Database },
  { href: "/approvals", label: "Approvals", icon: CheckSquare2 },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    api<{ user: User }>("/api/auth/me")
      .then((data) => setUser(data.user))
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) router.replace("/login");
      })
      .finally(() => setLoading(false));
  }, [router]);

  async function logout() {
    await api("/api/auth/logout", { method: "POST" }).catch(() => null);
    router.replace("/login");
  }

  if (loading) {
    return <div className="boot-screen"><div className="boot-mark">S</div><span>Opening Service Desk…</span></div>;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <div className="brand-mark">S</div>
          <div>
            <div className="brand-name">Service Desk</div>
            <div className="brand-org">{user?.organization}</div>
          </div>
        </div>

        <nav className="nav-list" aria-label="Main navigation">
          {nav.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link className={`nav-item ${active ? "active" : ""}`} href={href} key={href}>
                <Icon size={17} strokeWidth={1.8} />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-spacer" />
        <Link className={`nav-item ${pathname.startsWith("/settings") ? "active" : ""}`} href="/settings">
          <Settings size={17} strokeWidth={1.8} />
          <span>Settings</span>
        </Link>

        <div className="user-switcher">
          <button className="user-button" onClick={() => setMenuOpen((value) => !value)}>
            <span className="avatar">{user?.name?.split(" ").map((x) => x[0]).join("").slice(0, 2) || "U"}</span>
            <span className="user-copy">
              <strong>{user?.name || "Signed in"}</strong>
              <small>{user?.role || "member"}</small>
            </span>
            <ChevronDown size={15} />
          </button>
          {menuOpen && (
            <div className="user-menu">
              <div className="user-menu-meta">{user?.email}</div>
              <button onClick={logout}><LogOut size={15} /> Sign out</button>
            </div>
          )}
        </div>
      </aside>

      <main className="main-area">
        <header className="mobile-header">
          <Link className="mobile-brand" href="/work"><span className="brand-mark">S</span><strong>Service Desk</strong></Link>
          <div className="mobile-links">
            {nav.map(({ href, label }) => <Link key={href} href={href}>{label}</Link>)}
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}

export function StatusBadge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "good" | "warn" | "danger" | "blue" }) {
  return <span className={`status-badge ${tone}`}>{children}</span>;
}

export function PageTitle({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="page-title-row">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action && <div className="page-title-action">{action}</div>}
    </div>
  );
}

export function InlineLoader({ label = "Loading" }: { label?: string }) {
  return <div className="inline-loader"><Wrench size={16} className="spin-slow" /><span>{label}</span></div>;
}
