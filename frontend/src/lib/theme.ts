export type Theme = "dark" | "light";

const KEY = "fintrace-theme";

/** Dark is the default. The choice is a per-browser convenience, so storage failures are ignored. */
export function storedTheme(): Theme {
  try {
    return localStorage.getItem(KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    // Private mode or blocked storage: the theme still applies for this visit.
  }
}
