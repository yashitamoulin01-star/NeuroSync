import type { Metadata } from 'next'
import './globals.css'
import { Inter } from "next/font/google";
import { cn } from "@/lib/utils";
import { AuthProvider } from "@/lib/auth";

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });

export const metadata: Metadata = {
  title: {
    template: '%s — NeuroSync',
    default: 'NeuroSync · Behavioral Intelligence Platform',
  },
  description: 'NeuroSync — enterprise behavioral intelligence. Decode confidence, stress, and communication quality in real time with evidence-backed multimodal analysis.',
  keywords: ['behavioral intelligence', 'interview analysis', 'AI assessment', 'multimodal AI', 'NeuroSync', 'behavioral analytics'],
  authors: [{ name: 'NeuroSync Team' }],
  openGraph: {
    title: 'NeuroSync · Behavioral Intelligence Platform',
    description: 'Enterprise behavioral intelligence. Decode confidence, stress, and communication quality in real time.',
    type: 'website',
    locale: 'en_US',
    siteName: 'NeuroSync',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'NeuroSync · Behavioral Intelligence Platform',
    description: 'Enterprise behavioral intelligence. Decode confidence, stress, and communication quality in real time.',
  },
  robots: {
    index: true,
    follow: true,
  }
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={cn("dark", "font-sans", inter.variable)}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" crossOrigin="anonymous" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="bg-bg-base text-text-primary antialiased min-h-screen flex flex-col">
        <a href="#main-content" className="skip-link">
          Skip to main content
        </a>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  )
}
