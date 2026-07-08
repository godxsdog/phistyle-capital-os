#!/usr/bin/env node
/*
 * Browser-based AirAsia flight status probe.
 *
 * This is intentionally separate from tools/flight_watch.py. It opens the
 * official AirAsia flight status page, searches like a user, captures the
 * GetByFlightNumber JSON response, and prints a compact result.
 *
 * Run from the repo root:
 *   npm exec --yes --package playwright -- node tools/airasia_browser_status.js AK1511 2026-07-10
 *
 * Debug with a visible browser:
 *   HEADLESS=0 npm exec --yes --package playwright -- node tools/airasia_browser_status.js AK1511 2026-07-10
 */

const FLIGHT_STATUS_URL = "https://www.airasia.com/flightstatus/zh/tw";
const API_MARKER = "/GetByFlightNumber";

const flightNo = process.argv[2] || "AK1511";
const flightDate = process.argv[3] || "2026-07-10";
const headless = process.env.HEADLESS !== "0";

async function main() {
  let playwright;
  try {
    playwright = require("playwright");
  } catch (error) {
    console.error("找不到 Playwright。請用這個指令執行：");
    console.error(`npm exec --yes --package playwright -- node tools/airasia_browser_status.js ${flightNo} ${flightDate}`);
    process.exit(2);
  }

  const browser = await playwright.chromium.launch({ headless });
  const page = await browser.newPage({
    locale: "zh-TW",
    timezoneId: "Asia/Taipei",
    viewport: { width: 1366, height: 900 },
  });

  const apiResponses = [];
  page.on("response", async (response) => {
    const url = response.url();
    if (!url.includes(API_MARKER)) return;
    try {
      apiResponses.push({
        url,
        status: response.status(),
        json: await response.json(),
      });
    } catch (error) {
      apiResponses.push({
        url,
        status: response.status(),
        text: await response.text().catch(() => String(error)),
      });
    }
  });

  try {
    await page.goto(FLIGHT_STATUS_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
    await closeCookieBanner(page);
    await selectFlightNumberMode(page);
    await fillFlightNumber(page, flightNo);
    await fillFlightDate(page, flightDate);
    await clickSearch(page);
    await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => undefined);
    await page.waitForTimeout(3000);

    const api = apiResponses.at(-1);
    if (api) {
      console.log(JSON.stringify({
        source: "airasia_browser_network",
        flight_no: flightNo,
        flight_date: flightDate,
        http_status: api.status,
        api_url: api.url,
        summary: summarizePayload(api.json ?? api.text),
        raw: api.json ?? api.text,
      }, null, 2));
      return;
    }

    const visibleText = await page.locator("body").innerText({ timeout: 5000 }).catch(() => "");
    console.log(JSON.stringify({
      source: "airasia_browser_visible_text",
      flight_no: flightNo,
      flight_date: flightDate,
      warning: "沒有攔到 GetByFlightNumber JSON response，以下是頁面可見文字。",
      visible_text: visibleText.slice(0, 6000),
    }, null, 2));
  } finally {
    await browser.close();
  }
}

async function closeCookieBanner(page) {
  for (const label of [/accept/i, /agree/i, /同意/, /接受/, /允許/]) {
    const button = page.getByRole("button", { name: label }).first();
    if (await button.isVisible().catch(() => false)) {
      await button.click().catch(() => undefined);
      await page.waitForTimeout(500);
      return;
    }
  }
}

async function selectFlightNumberMode(page) {
  const candidates = [
    /航班號碼/,
    /航班編號/,
    /班機號碼/,
    /Flight number/i,
    /Flight no/i,
  ];
  for (const name of candidates) {
    const target = page.getByText(name).first();
    if (await target.isVisible().catch(() => false)) {
      await target.click().catch(() => undefined);
      await page.waitForTimeout(500);
      return;
    }
  }
}

async function fillFlightNumber(page, value) {
  const flightInput = page.locator("#flightNumber").first();
  if (await flightInput.isVisible().catch(() => false)) {
    await flightInput.fill(value);
    return;
  }
  const preferred = [
    page.getByPlaceholder(/航班|班機|Flight/i).first(),
    page.getByLabel(/航班|班機|Flight/i).first(),
  ];
  for (const locator of preferred) {
    if (await locator.isVisible().catch(() => false)) {
      await locator.fill(value);
      return;
    }
  }
  const inputs = await visibleInputs(page);
  if (inputs.length === 0) throw new Error("找不到可輸入航班號碼的欄位");
  await inputs[0].fill(value);
}

async function fillFlightDate(page, value) {
  const airAsiaDateInput = page.locator("#mat-input-0").first();
  if (await airAsiaDateInput.isVisible().catch(() => false)) {
    await chooseDateFromPicker(page, airAsiaDateInput, value);
    return;
  }
  const dateInput = page.locator('input[type="date"]').first();
  if (await dateInput.isVisible().catch(() => false)) {
    await dateInput.fill(value);
    return;
  }

  const preferred = [
    page.getByPlaceholder(/日期|date/i).first(),
    page.getByLabel(/日期|date/i).first(),
  ];
  for (const locator of preferred) {
    if (await locator.isVisible().catch(() => false)) {
      if (await locator.isEditable().catch(() => false)) {
        await locator.fill(value);
        await locator.press("Enter").catch(() => undefined);
      } else {
        await chooseDateFromPicker(page, locator, value);
      }
      return;
    }
  }

  const inputs = await visibleInputs(page);
  if (inputs.length >= 2) {
    let dateLike = inputs[1];
    for (const input of inputs) {
      const placeholder = await input.getAttribute("placeholder").catch(() => "");
      const calendar = await input.getAttribute("data-mat-calendar").catch(() => "");
      if (calendar || /date|日期/i.test(placeholder || "")) {
        dateLike = input;
        break;
      }
    }
    if (await dateLike.isEditable().catch(() => false)) {
      await dateLike.fill(value);
      await dateLike.press("Enter").catch(() => undefined);
    } else {
      await chooseDateFromPicker(page, dateLike, value);
    }
  }
}

async function chooseDateFromPicker(page, input, value) {
  const day = String(Number(value.slice(-2)));
  await input.click({ force: true });
  await page.waitForTimeout(500);
  const dayCell = page
    .locator(".mat-calendar-body-cell:not(.mat-calendar-body-disabled)")
    .filter({ hasText: new RegExp(`^\\s*${day}\\s*$`) })
    .first();
  if (await dayCell.isVisible().catch(() => false)) {
    await dayCell.click();
    await page.waitForTimeout(500);
    return;
  }
  throw new Error(`找不到日期選擇器中的 ${value}`);
}

async function clickSearch(page) {
  const airAsiaSearch = page.locator("button.findButton").filter({ hasText: /查找航班|Search|Find/i }).first();
  if (await airAsiaSearch.isVisible().catch(() => false)) {
    await airAsiaSearch.click();
    return;
  }
  const candidates = [
    /搜尋/,
    /查詢/,
    /Search/i,
    /Check/i,
  ];
  for (const name of candidates) {
    const button = page.getByRole("button", { name }).first();
    if (await button.isVisible().catch(() => false)) {
      await button.click();
      return;
    }
  }
  await page.keyboard.press("Enter");
}

async function visibleInputs(page) {
  const locators = [];
  const count = await page.locator("input").count();
  for (let index = 0; index < count; index += 1) {
    const input = page.locator("input").nth(index);
    const type = await input.getAttribute("type").catch(() => "");
    const id = await input.getAttribute("id").catch(() => "");
    if (/email|password/i.test(type || "") || /^sso-/i.test(id || "")) continue;
    if (await input.isVisible().catch(() => false)) locators.push(input);
  }
  return locators;
}

function summarizePayload(payload) {
  if (!payload || typeof payload !== "object") return String(payload ?? "");
  const text = JSON.stringify(payload);
  const statusMatch = text.match(/cancelled|delayed|on time|not yet departed|departed|landed|取消|延誤/i);
  return {
    likely_status: statusMatch ? statusMatch[0] : "未從 JSON 自動辨識",
    keys: Array.isArray(payload) ? ["array", `length=${payload.length}`] : Object.keys(payload).slice(0, 20),
    flights: Array.isArray(payload) ? payload.map(summarizeFlightRecord) : [],
  };
}

function summarizeFlightRecord(record) {
  return {
    flight: record.flightNumber || [record.flightCarrier, record.prev_flightnumber].filter(Boolean).join(" "),
    route: [record.flightDep, record.flightArr].filter(Boolean).join(" → "),
    status: record.flightStatus || record.status || record.statusName || "未知",
    departure: record.flight_dep_estimated_time || record.flight_dep_scheduled_time || record.utcFlightDepart || null,
    arrival: record.flight_arr_estimated_time || record.flight_arr_scheduled_time || record.utcFlightArrival || null,
    aircraft: record.rego || null,
    last_updated: record.lastUpdatedCache || null,
  };
}

main().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
