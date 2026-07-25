import type {Metadata} from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Published agent · Universal Agent Studio",
  description: "Run a published Universal Agent Studio agent.",
  robots: {index: false, follow: false},
};

export default function RootLayout({
  children,
}: Readonly<{children: React.ReactNode}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
