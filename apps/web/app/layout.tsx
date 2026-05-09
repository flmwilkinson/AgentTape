import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Source_Serif_4 } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { ThemeProvider } from "@/components/theme-provider";
import { QueryProvider } from "@/lib/query-provider";
import { CompareTrayLauncher } from "@/components/compare-tray";
import { GlobalKeyboardShortcuts } from "@/components/global-keyboard-shortcuts";
import { NavDesktop } from "@/components/nav-desktop";
import { NavMobile } from "@/components/nav-mobile";
import { NavMobileTop } from "@/components/nav-mobile-top";
import { SiteFooter } from "@/components/site-footer";
import { ToastHost } from "@/components/toast-host";
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

// Site-wide metadata. The default title is what the browser tab
// shows on the homepage and any page that doesn't set its own; the
// template prefixes nested page titles with the page name. Both feed
// directly into Google's SERP listing alongside the description.
//
// metadataBase tells Next how to resolve relative og:image URLs into
// absolute URLs for crawlers and social cards. Without it, Open Graph
// previews on LinkedIn / Twitter / Slack break for the homepage.
export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "https://agenttape.com",
  ),
  title: {
    default: "AgentTape: Live AI Agent Index",
    template: "%s | AgentTape",
  },
  description:
    "AgentTape is the live ranking of every public AI agent and foundation model. AgentScore tracks adoption, quality, momentum and community in real time, sourced only from public signals. Compare any two side by side. Free to read.",
  applicationName: "AgentTape",
  keywords: [
    "AI agents",
    "foundation models",
    "AI agent leaderboard",
    "AgentScore",
    "compare AI agents",
    "best AI coding agent",
    "best browser AI agent",
    "MCP servers",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "AgentTape",
    title: "AgentTape: Live AI Agent Index",
    description:
      "Live ranking of every public AI agent and foundation model. Updated hourly from public signals. Free to read, no login.",
    url: "/",
    images: [{ url: "/api/og/index/tape-100", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "AgentTape: Live AI Agent Index",
    description:
      "Live ranking of every public AI agent and foundation model. Updated hourly.",
    images: ["/api/og/index/tape-100"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-snippet": -1,
      "max-image-preview": "large",
      "max-video-preview": -1,
    },
  },
};

// Organization + WebSite structured data. Tells Google that the
// AgentTape brand has a logo (so the Knowledge Panel shows it next
// to search results) and that the site supports the "/search?q=…"
// pattern (so Google may show a sitelinks search box under the main
// listing). Fed once at the layout level so every page includes it.
const ORG_JSON_LD = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://agenttape.com#org",
      name: "AgentTape",
      url: "https://agenttape.com",
      logo: "https://agenttape.com/apple-icon",
      description:
        "Live, autonomously-populated index of every public AI agent and foundation model.",
      sameAs: ["https://github.com/flmwilkinson/AgentTape"],
    },
    {
      "@type": "WebSite",
      "@id": "https://agenttape.com#website",
      url: "https://agenttape.com",
      name: "AgentTape",
      publisher: { "@id": "https://agenttape.com#org" },
      potentialAction: {
        "@type": "SearchAction",
        target: {
          "@type": "EntryPoint",
          urlTemplate:
            "https://agenttape.com/search?q={search_term_string}",
        },
        "query-input": "required name=search_term_string",
      },
    },
  ],
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
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(ORG_JSON_LD) }}
        />
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
          <QueryProvider>
            <NavDesktop />
            <NavMobileTop />
            <GlobalKeyboardShortcuts />
            {/* Bottom nav adds 4rem space on mobile so content isn't covered. */}
            <main className="pb-16 md:pb-0">{children}</main>
            <SiteFooter />
            <NavMobile />
            <CompareTrayLauncher />
            <ToastHost />
          </QueryProvider>
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  );
}
