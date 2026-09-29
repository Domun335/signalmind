import { Geist, Geist_Mono, Inter } from 'next/font/google'
import './globals.css'
import { cn } from "@/lib/utils";

const inter = Inter({subsets:['latin'],variable:'--font-sans'});

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
})

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
})

export const metadata = {
  title: 'OutOfBlack // Tactical Swarm Reconnaissance',
  description: 'Dual-Use P2P Mesh UAV Swarm Reconnaissance & RF Victim Localization Command Dashboard',
}

export default function RootLayout({ children }) {
  return (
    <html lang="pl" className={cn("dark h-screen max-h-screen overflow-hidden antialiased", geistSans.variable, geistMono.variable, "font-sans", inter.variable)}>
      <body className="h-screen max-h-screen overflow-hidden flex flex-col bg-background text-foreground selection:bg-cyan-500/20 selection:text-cyan-400">{children}</body>
    </html>
  )
}
