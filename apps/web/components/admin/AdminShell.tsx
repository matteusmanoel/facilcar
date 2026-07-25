"use client";

import { useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { UserRole } from "@prisma/client";
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
  Tag,
  Contact,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { useLocalStorage } from "@/hooks/useLocalStorage";
import { ThemeToggle } from "@/components/admin/ThemeToggle";
import { getBottomNavPriority, getVisibleNavItems, type NavItemKey } from "@/features/auth/rbac-config";

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
    key: "clientes",
    href: "/admin/clientes",
    label: "Clientes",
    icon: Contact,
    matchPrefixes: ["/admin/clientes"],
  },
  { key: "marcas", href: "/admin/marcas", label: "Marcas", icon: Tag, matchPrefixes: ["/admin/marcas"] },
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
}: {
  item: NavItemDef;
  collapsed: boolean;
}) {
  const isActive = useNavActive(item.href, item.exact, item.matchPrefixes);
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
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

export function AdminShell({ children, signOutAction, role }: AdminShellProps) {
  const [collapsed, setCollapsed, isHydrated] = useLocalStorage("admin-sidebar-collapsed", false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleCollapse = useCallback(() => setCollapsed((v) => !v), [setCollapsed]);
  const isCollapsed = isHydrated ? collapsed : false;

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

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <aside
        className={cn(
          "hidden md:flex flex-col flex-shrink-0 border-r border-facil-border bg-facil-card transition-all duration-200 ease-in-out",
          isCollapsed ? "sidebar-collapsed" : "sidebar-expanded",
        )}
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
          <div className={cn("flex px-1 pb-1", isCollapsed && "justify-center")}>
            <ThemeToggle />
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
      </aside>

      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 flex-col border-r border-facil-border bg-facil-card transition-transform duration-200 md:hidden",
          mobileOpen ? "flex translate-x-0" : "-translate-x-full flex",
        )}
      >
        <div className="flex h-14 items-center justify-between border-b border-zinc-100 px-4 dark:border-zinc-800">
          <Link href="/admin" className="flex items-center gap-2" onClick={() => setMobileOpen(false)}>
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-facil-orange text-white text-xs font-bold">
              F
            </div>
            <span className="font-semibold text-zinc-900 dark:text-zinc-100">FácilCar Admin</span>
          </Link>
          <button
            onClick={() => setMobileOpen(false)}
            className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {navItems.map((item) => (
            <NavItem key={item.href} item={item} collapsed={false} />
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
      </aside>

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
