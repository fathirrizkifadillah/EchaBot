import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EchaBot — AI Data Analyst",
  description: "Upload dataset, tanya analisis, dapatkan insight instan.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="id" className="h-full antialiased">
      <body className="h-full overflow-hidden">{children}</body>
    </html>
  );
}
