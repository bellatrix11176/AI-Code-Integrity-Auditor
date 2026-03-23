import type { Metadata } from "next";
import { Inter, Instrument_Serif } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const instrumentSerif = Instrument_Serif({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-instrument",
});

export const metadata: Metadata = {
  title: "AI Code Integrity Auditor",
  description: "Detect hallucinations, drift, and silent failures in AI-generated code",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${instrumentSerif.variable} antialiased`}>
      <body className="min-h-screen selection:bg-accent/30 selection:text-white">
        <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-5 py-8 md:py-10">
          {children}
        </main>
      </body>
    </html>
  );
}
