// Capture the README screenshots from a running FinTrace stack. Read-only: it signs in and looks, it changes nothing.
//
//   FINTRACE_URL               default http://localhost:8080 (Docker Compose); use http://localhost:5173 for `npm run dev`
//   FINTRACE_SHOT_EMAIL        default demo.analyst@example.com
//   FINTRACE_SHOT_PASSWORD     default $FINTRACE_DEMO_PASSWORD
//   FINTRACE_SHOT_SENIOR_EMAIL default demo.senior@example.com (for the audit log; same password)
//   CHROMIUM_PATH              a Chromium/Chrome binary; otherwise the installed Chrome (or set PW_CHANNEL=msedge)
//   output: ../docs/screenshots (override with FINTRACE_SHOT_DIR)
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const base = (process.env.FINTRACE_URL ?? "http://localhost:8080").replace(/\/$/, "");
const email = process.env.FINTRACE_SHOT_EMAIL ?? "demo.analyst@example.com";
const seniorEmail = process.env.FINTRACE_SHOT_SENIOR_EMAIL ?? "demo.senior@example.com";
const password = process.env.FINTRACE_SHOT_PASSWORD ?? process.env.FINTRACE_DEMO_PASSWORD;
const out = resolve(process.env.FINTRACE_SHOT_DIR ?? resolve(dirname(fileURLToPath(import.meta.url)), "../../docs/screenshots"));
if (!password) {
  console.error("Set FINTRACE_SHOT_PASSWORD (or FINTRACE_DEMO_PASSWORD) to the demo users' password.");
  process.exit(2);
}

await mkdir(out, { recursive: true });
const browser = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : { channel: process.env.PW_CHANNEL ?? "chrome" },
);
const problems = [];

async function signIn(user, { theme, ...options } = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, ...options });
  if (theme) await context.addInitScript((t) => localStorage.setItem("fintrace-theme", t), theme);
  const page = await context.newPage();
  page.on("pageerror", (e) => problems.push(`${page.url()}: ${e.message}`));
  page.on("response", (r) => r.url().includes("/api/") && r.status() >= 500 && problems.push(`${r.status()} ${r.url()}`));
  await page.goto(`${base}/`);
  await page.getByLabel("Email").fill(user);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("heading", { name: "Overview" }).waitFor();
  return page;
}

async function shot(page, name, { full = true } = {}) {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(500); // let entrance animations settle
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: full });
  console.log(`saved ${name}.png`);
}

// Sign-in page, after the trace line has drawn.
{
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${base}/`);
  await page.waitForTimeout(3200);
  await shot(page, "01-login", { full: false });
  await page.close();
}

const a = await signIn(email);
await a.getByRole("img", { name: "Histogram of risk scores" }).waitFor();
await shot(a, "02-overview");

await a.goto(`${base}/alerts`);
await a.locator("tbody tr").first().waitFor();
await shot(a, "03-alert-queue", { full: false });

await a.locator("tbody tr td:nth-child(2) a").first().click();
await a.getByRole("heading", { name: /Alert #\d+/ }).waitFor();
await shot(a, "04-alert-detail");

await a.goto(`${base}/cases`);
await a.locator("tbody tr, .state-empty").first().waitFor();
const firstCase = a.locator("tbody tr td a").first();
if (await firstCase.count()) {
  await firstCase.click();
  await a.getByRole("heading", { name: /CASE-\d+/ }).waitFor();
  await shot(a, "05-case");
}

await a.goto(`${base}/transactions`);
await a.locator("tbody tr").first().waitFor();
await shot(a, "06-transactions", { full: false });

await a.goto(`${base}/model`);
await a.getByRole("img", { name: "Histogram of risk scores" }).waitFor();
await shot(a, "07-model");

await a.goto(`${base}/rules`);
await a.getByRole("heading", { name: "Monitoring rules" }).waitFor();
await shot(a, "08-rules");

const s = await signIn(seniorEmail);
await s.goto(`${base}/audit`);
await s.locator("tbody tr").first().waitFor();
await shot(s, "09-audit-log", { full: false });

const light = await signIn(email, { theme: "light" });
await light.getByRole("img", { name: "Histogram of risk scores" }).waitFor();
await shot(light, "10-overview-light", { full: false });

const phone = await signIn(email, { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
await phone.getByRole("img", { name: "Histogram of risk scores" }).waitFor();
await shot(phone, "11-overview-phone", { full: false });

await browser.close();
if (problems.length) {
  console.error("Problems seen while capturing:\n" + problems.join("\n"));
  process.exit(1);
}
