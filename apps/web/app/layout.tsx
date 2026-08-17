import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Service Desk",
  description: "Helps service teams review problems and approve work",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
