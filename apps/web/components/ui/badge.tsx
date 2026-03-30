import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
  {
    variants: {
      variant: {
        default: "bg-zinc-100 text-zinc-700",
        primary: "bg-facil-orange-light text-facil-orange",
        blue: "bg-blue-100 text-blue-800",
        yellow: "bg-yellow-100 text-yellow-800",
        green: "bg-green-100 text-green-800",
        red: "bg-red-100 text-red-700",
        purple: "bg-purple-100 text-purple-800",
        indigo: "bg-indigo-100 text-indigo-800",
        outline: "border border-zinc-200 text-zinc-700",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
