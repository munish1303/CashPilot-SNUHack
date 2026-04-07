import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "./components/Sidebar";

export const metadata: Metadata = {
  title: "CashPilot — Autopilot Command Center",
};

import { SimulationProvider } from "./context/SimulationContext";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased flex">
        <SimulationProvider>
          <Sidebar />
          <main className="flex-1 overflow-y-auto min-h-screen">{children}</main>
        </SimulationProvider>
      </body>
    </html>
  );
}
