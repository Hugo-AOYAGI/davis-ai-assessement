"use client";

import { useEffect } from "react";

/** Applies `?theme=dark|light` to the root element, for screenshots. */
export function ThemeFromQuery() {
  useEffect(() => {
    const theme = new URLSearchParams(window.location.search).get("theme");
    if (theme === "dark" || theme === "light") {
      document.documentElement.classList.toggle("dark", theme === "dark");
    }
  }, []);
  return null;
}
