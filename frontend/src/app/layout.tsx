import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { ThemeToggle } from '@/components/ThemeToggle';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Ayush Habba - Personalized Ayurvedic Wellness',
  description: 'AI-powered Ayurvedic treatment recommendations based on your unique Prakriti constitution.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        {/* Skip to main content link for accessibility */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-[60] focus:px-4 focus:py-2 focus:bg-ayurveda-gold focus:text-white focus:rounded-lg focus:outline-none"
        >
          Skip to main content
        </a>
        <div className="min-h-screen bg-gradient-to-br from-amber-50 via-white to-green-50 dark:from-gray-900 dark:via-gray-950 dark:to-gray-900">
          <ThemeToggle />
          {children}
        </div>
      </body>
    </html>
  );
}
