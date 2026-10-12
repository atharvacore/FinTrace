import { useState } from "react";
import { applyTheme, storedTheme, type Theme } from "../lib/theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(storedTheme);
  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      className="btn btn-small btn-ghost theme-toggle"
      onClick={() => {
        applyTheme(next);
        setTheme(next);
      }}
    >
      {next === "light" ? "Light theme" : "Dark theme"}
    </button>
  );
}
