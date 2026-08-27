"use client";

import { useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { UserRole } from "@prisma/client";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  LayoutDashboard,
  Car,
  Users,
  UserCog,
  FileText,
  BookOpen,
  Settings,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { useLocalStorage } from "@/hooks/useLocalStorage";
import { ThemeToggle } from "@/components/admin/ThemeToggle";
import { SdrNotificationBadge } from "@/components/admin/SdrNotificationBadge";
import { getBottomNavPriority, getVisibleNavItems, LEAD_ROLES, type NavItemKey } from "@/features/auth/rbac-config";

type NavItemDef = {
  key: NavItemKey;
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
  matchPrefixes?: string[];
};

const ALL_NAV_ITEMS: NavItemDef[] = [
  { key: "dashboard", href: "/admin", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { key: "veiculos", href: "/admin/veiculos", label: "Veículos", icon: Car },
  {
    key: "leads",
    href: "/admin/leads",
    label: "Leads & CRM",
    icon: Users,
    matchPrefixes: ["/admin/leads", "/admin/crm"],
  },
  {
    key: "usuarios",
    href: "/admin/usuarios",
    label: "Usuários",
    icon: UserCog,
    matchPrefixes: ["/admin/usuarios"],
  },
  { key: "paginas", href: "/admin/paginas", label: "Páginas", icon: FileText },
  { key: "blog", href: "/admin/blog", label: "Blog", icon: BookOpen },
  { key: "configuracoes", href: "/admin/configuracoes", label: "Configurações", icon: Settings },
];

function useNavActive(href: string, exact?: boolean, matchPrefixes?: string[]) {
  const pathname = usePathname();
  if (exact) return pathname === href;
  if (matchPrefixes) return matchPrefixes.some((p) => pathname.startsWith(p));
  return pathname.startsWith(href);
}

function NavItem({
  item,
  collapsed,
  onNavigate,
}: {
  item: NavItemDef;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const isActive = useNavActive(item.href, item.exact, item.matchPrefixes);
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      title={collapsed ? item.label : undefined}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
        isActive
          ? "bg-facil-orange text-white"
          : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100",
        collapsed && "justify-center px-2",
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span className="truncate">{item.label}</span>}
    </Link>
  );
}

function BottomNavItem({ item }: { item: NavItemDef }) {
  const isActive = useNavActive(item.href, item.exact, item.matchPrefixes);
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      className={cn(
        "flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-xs font-medium transition-colors",
        isActive ? "text-facil-orange" : "text-zinc-500",
      )}
    >
      <Icon className={cn("h-5 w-5", isActive && "text-facil-orange")} />
      <span>{item.label}</span>
    </Link>
  );
}

interface AdminShellProps {
  children: React.ReactNode;
  signOutAction: () => Promise<void>;
  role: UserRole;
}

const SIDEBAR_EXPANDED = 240;
const SIDEBAR_COLLAPSED = 72;

export function AdminShell({ children, signOutAction, role }: AdminShellProps) {
  const [collapsed, setCollapsed, isHydrated] = useLocalStorage("admin-sidebar-collapsed", false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const reduceMotion = useReducedMotion();

  const toggleCollapse = useCallback(() => setCollapsed((v) => !v), [setCollapsed]);
  const isCollapsed = isHydrated ? collapsed : false;
  const sidebarWidth = isCollapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED;

  const navItems = useMemo(() => {
    const visible = new Set(getVisibleNavItems(role));
    return ALL_NAV_ITEMS.filter((item) => visible.has(item.key));
  }, [role]);

  const bottomNavItems = useMemo(() => {
    const priority = getBottomNavPriority(role);
    return priority
      .map((key) => navItems.find((item) => item.key === key))
      .filter((item): item is NavItemDef => !!item)
      .slice(0, 5);
  }, [navItems, role]);

  const closeMobile = useCallback(() => setMobileOpen(false), []);
  const showSdrBadge = (LEAD_ROLES as readonly UserRole[]).includes(role);

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <motion.aside
        className="hidden md:flex flex-col flex-shrink-0 border-r border-facil-border bg-facil-card overflow-hidden"
        initial={false}
        animate={{ width: reduceMotion ? sidebarWidth : sidebarWidth }}
        transition={{ type: "spring", stiffness: 420, damping: 38, mass: 0.7 }}
      >
        <div
          className={cn(
            "flex h-14 items-center border-b border-zinc-100 px-3 dark:border-zinc-800",
            isCollapsed ? "justify-center" : "justify-between",
          )}
        >
          {!isCollapsed && (
            <Link href="/admin" className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-facil-orange text-white text-xs font-bold">
                F
              </div>
              <span className="font-semibold text-zinc-900 text-sm dark:text-zinc-100">FácilCar</span>
            </Link>
          )}
          <button
            onClick={toggleCollapse}
            className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
            title={isCollapsed ? "Expandir menu" : "Recolher menu"}
          >
            {isCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {navItems.map((item) => (
            <NavItem key={item.href} item={item} collapsed={isCollapsed} />
          ))}
        </nav>

        <div className={cn("border-t border-zinc-100 p-2 space-y-0.5 dark:border-zinc-800")}>
          <div
            className={cn(
              "flex items-center gap-1 px-1 pb-1",
              isCollapsed ? "justify-center flex-col" : "justify-between",
            )}
          >
            <ThemeToggle />
            {showSdrBadge ? <SdrNotificationBadge /> : null}
          </div>
          <Link
            href="/"
            target="_blank"
            title={isCollapsed ? "Ver site" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700 transition-colors dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200",
              isCollapsed && "justify-center px-2",
            )}
          >
            <ExternalLink className="h-4 w-4 shrink-0" />
            {!isCollapsed && <span>Ver site</span>}
          </Link>
          <form action={signOutAction}>
            <button
              type="submit"
              title={isCollapsed ? "Sair" : undefined}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors dark:text-red-400 dark:hover:bg-red-950/30",
                isCollapsed && "justify-center px-2",
              )}
            >
              <LogOut className="h-4 w-4 shrink-0" />
              {!isCollapsed && <span>Sair</span>}
            </button>
          </form>
        </div>
      </motion.aside>

      <AnimatePresence>
        {mobileOpen ? (
          <>
            <motion.div
              key="mobile-overlay"
              className="fixed inset-0 z-40 bg-black/50 md:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: reduceMotion ? 0 : 0.2 }}
              onClick={closeMobile}
            />
            <motion.aside
              key="mobile-drawer"
              className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-facil-border bg-facil-card md:hidden"
              initial={reduceMotion ? false : { x: "-100%" }}
              animate={{ x: 0 }}
              exit={reduceMotion ? undefined : { x: "-100%" }}
              transition={
                reduceMotion
                  ? { duration: 0 }
                  : { type: "spring", stiffness: 380, damping: 36, mass: 0.85 }
              }
            >
              <div className="flex h-14 items-center justify-between border-b border-zinc-100 px-4 dark:border-zinc-800">
                <Link href="/admin" className="flex items-center gap-2" onClick={closeMobile}>
                  <div className="flex h-7 w-7 items-center justify-center rounded-md bg-facil-orange text-white text-xs font-bold">
                    F
                  </div>
                  <span className="font-semibold text-zinc-900 dark:text-zinc-100">FácilCar Admin</span>
                </Link>
                <button
                  onClick={closeMobile}
                  className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <nav className="flex-1 overflow-y-auto p-2 space-y-0.5">
                {navItems.map((item) => (
                  <NavItem key={item.href} item={item} collapsed={false} onNavigate={closeMobile} />
                ))}
              </nav>
              <div className="border-t border-zinc-100 p-2 space-y-0.5 dark:border-zinc-800">
                <Link
                  href="/"
                  target="_blank"
                  className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-zinc-500 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
                >
                  <ExternalLink className="h-4 w-4" />
                  <span>Ver site</span>
                </Link>
                <form action={signOutAction}>
                  <button
                    type="submit"
                    className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/30"
                  >
                    <LogOut className="h-4 w-4" />
                    <span>Sair</span>
                  </button>
                </form>
              </div>
            </motion.aside>
          </>
        ) : null}
      </AnimatePresence>

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 items-center gap-2 border-b border-facil-border bg-facil-card px-4 md:hidden">
          <button
            onClick={() => setMobileOpen(true)}
            className="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-facil-orange text-white text-xs font-bold">
              F
            </div>
            <span className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              FácilCar Admin
            </span>
          </div>
          {showSdrBadge ? <SdrNotificationBadge /> : null}
          <ThemeToggle />
        </header>

        <main className="flex-1 overflow-y-auto pb-20 md:pb-0">{children}</main>
      </div>

      <nav className="fixed bottom-0 inset-x-0 z-30 flex border-t border-facil-border bg-facil-card md:hidden">
        {bottomNavItems.map((item) => (
          <BottomNavItem key={item.href} item={item} />
        ))}
      </nav>
    </div>
  );
}
