"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function Nav() {
  const { user, isCoordinator, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [alertCount, setAlertCount] = useState(0);

  const refreshBadge = useCallback(() => {
    api("/alerts")
      .then((data) => setAlertCount(data.count))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!user) {
      setAlertCount(0);
      return undefined;
    }
    refreshBadge();
    const timer = setInterval(refreshBadge, 60000);
    window.addEventListener("vs-data-changed", refreshBadge);
    return () => {
      clearInterval(timer);
      window.removeEventListener("vs-data-changed", refreshBadge);
    };
  }, [user, refreshBadge]);

  if (!user) return null;

  const links = [
    { href: "/", label: "Dashboard" },
    { href: "/shifts", label: "Shifts" },
    { href: "/programs", label: "Programs" },
    ...(isCoordinator ? [{ href: "/people", label: "People" }] : []),
  ];
  const active = (href) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <header className="nav">
      <div className="nav-inner">
        <Link href="/" className="brand">
          Volunteer Scheduling
        </Link>
        <nav aria-label="Main">
          {links.map((l) => (
            <Link key={l.href} href={l.href} className={active(l.href) ? "active" : ""}>
              {l.label}
            </Link>
          ))}
          <Link href="/alerts" className={active("/alerts") ? "active" : ""}>
            Alerts
            {alertCount > 0 && (
              <span className="count-badge" aria-label={`${alertCount} understaffed shifts`}>
                {alertCount}
              </span>
            )}
          </Link>
        </nav>
        <div className="who">
          <span>
            {user.name} <small className="muted">({user.role})</small>
          </span>
          <button
            onClick={() => {
              logout();
              router.replace("/login");
            }}
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
