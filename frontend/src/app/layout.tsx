import type { Metadata } from "next";
import "@ant-design/v5-patch-for-react-19";
import "./globals.css";

export const metadata: Metadata = {
  title: "Intelligent Data Agent",
  description: "Natural-language data analysis workspace",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
