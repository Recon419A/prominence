import type { Metadata, Viewport } from "next";
import { Fraunces, IBM_Plex_Mono, Libre_Franklin } from "next/font/google";
import "./globals.css";

const display = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
  axes: ["opsz", "SOFT"],
});

const body = Libre_Franklin({
  variable: "--font-body",
  subsets: ["latin"],
});

const mono = IBM_Plex_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Prominence — a topographic survey of human population",
  description:
    "Population density rendered as terrain. Prominence, key cols and the divide tree decide what counts as a city and whether two of them make a megalopolis.",
};

export const viewport: Viewport = {
  themeColor: "#f3ecd9",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${display.variable} ${body.variable} ${mono.variable} h-full`}
    >
      <body className="h-full">{children}</body>
    </html>
  );
}
