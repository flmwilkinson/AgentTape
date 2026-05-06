import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Source_Serif_4 } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import { QueryProvider } from "@/lib/query-provider";
import { CompareTrayLauncher } from "@/components/compare-tray";
import { NavDesktop } from "@/components/nav-desktop";
import { NavMobile } from "@/components/nav-mobile";
import { NavMobileTop } from "@/components/nav-mobile-top";
import "./globals.css";

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const serif = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-serif",
  display: "swap",
  // Editorial sizes only — no display weights.
  weight: ["400", "600"],
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "AgentTape", template: "%s — AgentTape" },
  description:
    "The live, autonomously-populated index of AI agents. Stars, downloads, benchmarks, mentions — ticking in real time.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${sans.variable} ${serif.variable} ${mono.variable}`}
    >
      <body className="min-h-screen bg-background text-foreground antialiased">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
          <QueryProvider>
            <NavDesktop />
            <NavMobileTop />
            {/* Bottom nav adds 4rem space on mobile so content isn't covered. */}
            <main className="pb-16 md:pb-0">{children}</main>
            <NavMobile />
            <CompareTrayLauncher />
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
