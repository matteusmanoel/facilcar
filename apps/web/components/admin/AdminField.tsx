import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export function AdminFieldLabel({
  children,
  required,
  htmlFor,
  className,
}: {
  children: React.ReactNode;
  required?: boolean;
  htmlFor?: string;
  className?: string;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className={cn("block text-sm font-medium text-foreground", className)}
    >
      {children}
      {required ? <span className="ml-1 text-facil-orange">*</span> : null}
    </label>
  );
}

export function AdminFieldError({ message, className }: { message?: string; className?: string }) {
  if (!message) return null;
  return <p className={cn("mt-1 text-xs text-red-500", className)}>{message}</p>;
}

export const AdminTextarea = forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full rounded-lg border border-facil-border bg-facil-card px-3 py-2 text-sm text-foreground shadow-sm transition-colors",
      "placeholder:text-facil-muted",
      "focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-facil-orange/30",
      "disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...props}
  />
));
AdminTextarea.displayName = "AdminTextarea";
