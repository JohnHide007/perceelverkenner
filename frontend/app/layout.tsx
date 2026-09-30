import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Perceelverkenner",
  description: "Klik een perceel aan en zie wat erop staat.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="nl" className="h-full antialiased">
      <body className="h-full">{children}</body>
    </html>
  );
}
