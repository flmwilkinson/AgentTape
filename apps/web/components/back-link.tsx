import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";

// "Up one level" navigation pill for detail pages.
//
// Lives at the top of every detail-flavoured page so a reader can
// always step back to the listing without using the browser back
// button (which doesn't exist when you land on the page from a
// shared link).

interface Props {
  href: string;
  label: string;
  className?: string;
}

export function BackLink({ href, label, className }: Props) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex items-center gap-1.5 text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:text-foreground",
        className,
      )}
    >
      <ChevronLeft className="h-3.5 w-3.5" />
      {label}
    </Link>
  );
}
