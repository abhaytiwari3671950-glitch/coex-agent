import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import type { ReactNode } from "react";
import { Analytics } from '@vercel/analytics/next';
import { TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import "./globals.css";
import "./modern.css";
const sans = Geist({ variable: "--font-sans", subsets: ["latin"], weight: "variable", display: "swap" });
const mono = Geist_Mono({ variable: "--font-mono", subsets: ["latin"], weight: "variable", display: "swap" });
export const metadata: Metadata = { title: "coex — Your space to think", description: "Think, write, code, and explore ideas with coex." };
export default function RootLayout({ children }: { readonly children: ReactNode }) {
  return <html className={cn("dark", sans.variable, mono.variable)} lang="en"><body><TooltipProvider>{children}</TooltipProvider><Analytics /></body></html>;
}