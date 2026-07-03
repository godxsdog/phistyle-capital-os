const hotelPrograms = ["Marriott", "Choice", "Hilton", "IHG", "Accor"];
const airlinePrograms = [
  "ANA",
  "EVA Air",
  "China Airlines",
  "Qatar Avios",
  "Finnair Avios",
  "British Airways Avios",
  "Asia Miles",
  "JAL",
  "Alaska",
  "Air Canada Aeroplan",
  "United",
  "LifeMiles",
  "Flying Blue",
];

const defaultAccounts = {
  kai: [...hotelPrograms.map(program => account("hotel", program)), ...airlinePrograms.map(program => account("airline", program))],
  wife: [...hotelPrograms.map(program => account("hotel", program)), ...airlinePrograms.map(program => account("airline", program))],
};

const state = {
  owner: "kai",
  view: "awardCost",
  rates: { TWD: 1, CNY: 4.35, USD: 31.5, JPY: 0.21, EUR: 34, GBP: 40, HKD: 4.03, CAD: 23, AUD: 20.6 },
  transferRules: [],
  pinganRules: { programs: [], assumptions: {} },
  officialCosts: { programs: [], source: "manual" },
  editingId: null,
  data: loadData(),
};

let dataSaveTimer = null;
let pinganSaveTimer = null;
let officialSaveTimer = null;
const expiryNotifyEmail = "haappyy114@gmail.com";

const $ = selector => document.querySelector(selector);
const $$ = selector => Array.from(document.querySelectorAll(selector));

function account(category, program) {
  return {
    id: createId(),
    category,
    program,
    balance: 0,
    costPerPoint: 0,
    expiryDate: "",
    note: "",
  };
}

function createId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `id-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function loadData() {
  const stored = localStorage.getItem("pointsWallet.v1");
  if (!stored) {
    return {
      accounts: defaultAccounts,
      quotes: { kai: [], wife: [] },
      transfers: { kai: [], wife: [] },
      awardCosts: { kai: [], wife: [] },
      marriottRules: [],
      pinganDisplayPresets: {},
      marriottCostSettings: { source: "wanlitong", manualCost: 0 },
    };
  }
  const parsed = JSON.parse(stored);
  return {
    accounts: {
      kai: parsed.accounts?.kai?.length ? parsed.accounts.kai : defaultAccounts.kai,
      wife: parsed.accounts?.wife?.length ? parsed.accounts.wife : defaultAccounts.wife,
    },
    quotes: {
      kai: parsed.quotes?.kai || [],
      wife: parsed.quotes?.wife || [],
    },
    transfers: {
      kai: parsed.transfers?.kai || [],
      wife: parsed.transfers?.wife || [],
    },
    awardCosts: {
      kai: parsed.awardCosts?.kai || [],
      wife: parsed.awardCosts?.wife || [],
    },
    marriottRules: parsed.marriottRules || [],
    pinganDisplayPresets: parsed.pinganDisplayPresets || {},
    marriottCostSettings: parsed.marriottCostSettings || { source: "wanlitong", manualCost: 0 },
  };
}

function saveData() {
  localStorage.setItem("pointsWallet.v1", JSON.stringify(state.data));
  syncRemoteData();
}

function scheduleSaveData() {
  clearTimeout(dataSaveTimer);
  dataSaveTimer = setTimeout(() => {
    saveData();
    $("#rateStatus").textContent = `已自動儲存 ${new Date().toLocaleTimeString("zh-TW")}`;
  }, 600);
}

async function loadRemoteData() {
  try {
    const response = await fetch("/api/data", { cache: "no-store" });
    if (!response.ok) return;
    const remote = await response.json();
    if (remote?.accounts?.kai || remote?.accounts?.wife) {
      state.data = {
        accounts: {
          kai: remote.accounts?.kai?.length ? remote.accounts.kai : state.data.accounts.kai,
          wife: remote.accounts?.wife?.length ? remote.accounts.wife : state.data.accounts.wife,
        },
        quotes: {
          kai: remote.quotes?.kai || [],
          wife: remote.quotes?.wife || [],
        },
        transfers: {
          kai: remote.transfers?.kai || [],
          wife: remote.transfers?.wife || [],
        },
        awardCosts: {
          kai: remote.awardCosts?.kai || [],
          wife: remote.awardCosts?.wife || [],
        },
        marriottRules: remote.marriottRules || state.data.marriottRules || [],
        pinganDisplayPresets: remote.pinganDisplayPresets || state.data.pinganDisplayPresets || {},
        marriottCostSettings: remote.marriottCostSettings || state.data.marriottCostSettings || { source: "wanlitong", manualCost: 0 },
      };
      localStorage.setItem("pointsWallet.v1", JSON.stringify(state.data));
      render();
    }
  } catch {
    $("#rateStatus").textContent = "本機模式：資料存在此瀏覽器";
  }
}

async function syncRemoteData() {
  try {
    await fetch("/api/data", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.data),
    });
  } catch {
    // Keep localStorage as an offline fallback.
  }
}

function money(value) {
  return `TWD ${Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function unitMoney(value) {
  return `TWD ${Number(value || 0).toFixed(2)}`;
}

function points(value) {
  return Math.round(value || 0).toLocaleString("en-US");
}

function daysUntil(dateText) {
  if (!dateText) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(`${dateText}T00:00:00`);
  return Math.ceil((target - today) / 86400000);
}

function currentAccounts() {
  return state.data.accounts[state.owner] || [];
}

function currentQuotes() {
  return state.data.quotes[state.owner] || [];
}

function currentTransfers() {
  if (!state.data.transfers) state.data.transfers = { kai: [], wife: [] };
  if (!state.data.transfers[state.owner]) state.data.transfers[state.owner] = [];
  return state.data.transfers[state.owner];
}

function currentAwardCosts() {
  if (!state.data.awardCosts) state.data.awardCosts = { kai: [], wife: [] };
  if (!state.data.awardCosts[state.owner]) state.data.awardCosts[state.owner] = [];
  return state.data.awardCosts[state.owner];
}

function categoryLabel(category) {
  return category === "hotel" ? "飯店" : "航空";
}

function pointUnitLabel(category) {
  return category === "hotel" ? "點" : "哩";
}

function render() {
  renderSummary();
  renderAccounts();
  renderQuotePrograms();
  renderQuote();
  renderQuoteHistory();
  renderAwardPrograms();
  renderAwardCost();
  renderPinganEditor();
  renderPinganDashboard();
  renderMarriottRules();
  renderOfficialCosts();
  renderTransferPrograms();
  renderTransfer();
  renderTransferHistory();
  renderExpiry();
}

function renderSummary() {
  const accounts = currentAccounts();
  const totalPoints = accounts.reduce((sum, item) => sum + Number(item.balance || 0), 0);
  const totalCost = accounts.reduce((sum, item) => sum + Number(item.balance || 0) * Number(item.costPerPoint || 0), 0);
  const expiring = accounts.filter(item => {
    const days = daysUntil(item.expiryDate);
    return days !== null && days >= 0 && days <= 180;
  }).length;
  $("#totalPoints").textContent = points(totalPoints);
  $("#totalCost").textContent = money(totalCost);
  $("#expiringCount").textContent = String(expiring);
}

function renderAccounts() {
  const list = $("#accountList");
  list.replaceChildren();
  const template = $("#accountTemplate");
  currentAccounts().forEach(item => {
    const node = template.content.cloneNode(true);
    const unitLabel = pointUnitLabel(item.category);
    const totalCost = Number(item.balance || 0) * Number(item.costPerPoint || 0);
    const row = node.querySelector(".account-row");
    row.dataset.id = item.id;
    node.querySelector('[data-field="category"]').value = item.category;
    populateInlineProgramSelect(node.querySelector(".account-program-select"), item.category, item.program);
    node.querySelector('[data-field="balance"]').value = Number(item.balance || 0);
    node.querySelector('[data-field="costPerPoint"]').value = Number(item.costPerPoint || 0).toFixed(2);
    node.querySelector('[data-field="expiryDate"]').value = item.expiryDate || "";
    node.querySelector(".cost").textContent = `加總成本 ${money(totalCost)}`;
    node.querySelector(".delete-account-button").addEventListener("click", () => deleteAccountById(item.id));
    list.append(node);
  });
}

function populateInlineProgramSelect(select, category, selected) {
  const programs = category === "hotel" ? hotelPrograms : airlinePrograms;
  select.replaceChildren();
  programs.forEach(program => {
    const option = document.createElement("option");
    option.value = program;
    option.textContent = program;
    select.append(option);
  });
  if (programs.includes(selected)) select.value = selected;
}

function renderQuotePrograms() {
  const select = $("#quoteProgram");
  const current = select.value;
  select.replaceChildren();
  currentAccounts().forEach(item => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = `${item.program} (${categoryLabel(item.category)})`;
    select.append(option);
  });
  if (current && currentAccounts().some(item => item.id === current)) select.value = current;
}

function selectedQuoteAccount() {
  return currentAccounts().find(item => item.id === $("#quoteProgram").value) || currentAccounts()[0];
}

function taxInTwd() {
  const amount = Number($("#quoteTax").value || 0);
  const currency = $("#quoteCurrency").value;
  return amount * Number(state.rates[currency] || 1);
}

function transferTaxInTwd() {
  const amount = Number($("#transferTax").value || 0);
  const currency = $("#transferCurrency").value;
  return amount * Number(state.rates[currency] || 1);
}

function renderQuote() {
  const account = selectedQuoteAccount();
  if (!account) {
    $("#quoteResult").textContent = "請先新增帳戶。";
    return;
  }
  const usedPoints = Number($("#quotePoints").value || 0);
  const pointCost = usedPoints * Number(account.costPerPoint || 0);
  const taxes = taxInTwd();
  const totalCost = pointCost + taxes;
  const cashValue = Number($("#cashValue").value || 0);
  const savings = cashValue ? cashValue - totalCost : 0;
  const cpp = usedPoints ? ((cashValue - taxes) / usedPoints) : 0;
  $("#quoteResult").innerHTML = `
    <span>${account.program}</span>
    <strong>實際成本 ${money(totalCost)}</strong>
    <span>點數成本 ${money(pointCost)} + 稅金 ${money(taxes)}</span>
    <span>${cashValue ? `相對現金價省 ${money(savings)}，每點價值 TWD ${cpp.toFixed(2)}` : "填入現金價值後可估算省多少"}</span>
  `;
}

function renderAwardPrograms() {
  const select = $("#awardProgram");
  if (!select) return;
  const current = select.value;
  select.replaceChildren();
  airlinePrograms.forEach(program => {
    const option = document.createElement("option");
    option.value = program;
    option.textContent = program;
    select.append(option);
  });
  if (current && Array.from(select.options).some(option => option.value === current)) select.value = current;
}

function selectedAwardAccount() {
  const program = $("#awardProgram")?.value;
  return currentAccounts().find(item => item.program === program) || null;
}

function accountForProgram(program) {
  return currentAccounts().find(item => item.program === program) || null;
}

function sourceToProgram(source) {
  const map = {
    aeroplan: "Air Canada Aeroplan",
    alaska: "Alaska",
    lifemiles: "LifeMiles",
    united: "United",
    flyingblue: "Flying Blue",
    ba: "British Airways Avios",
    britishairways: "British Airways Avios",
    asia: "Asia Miles",
  };
  return map[String(source || "").toLowerCase()] || "";
}

function awardTaxInTwd() {
  const amount = Number($("#awardTax").value || 0);
  const currency = $("#awardCurrency").value;
  return amount * Number(state.rates[currency] || 1);
}

function airlineRule(program, bonusMode = "bonus") {
  const rule = state.transferRules.find(item => item.program === program);
  if (rule) {
    return bonusMode === "none" ? { ...rule, bonusThreshold: 0, bonusMiles: 0 } : rule;
  }
  if (airlinePrograms.includes(program)) {
    const hasBonus = bonusMode !== "none" && program !== "LifeMiles";
    return { program, category: "airline", ratio: 3, bonusThreshold: hasBonus ? 60000 : 0, bonusMiles: hasBonus ? 5000 : 0 };
  }
  return null;
}

function marriottNeededForMiles(targetMiles, rule) {
  if (!targetMiles || !rule?.ratio) return 0;
  const max = Math.ceil(targetMiles * Number(rule.ratio || 3) + 180000);
  for (let marriottPoints = 1000; marriottPoints <= max; marriottPoints += 1000) {
    if (transferredMiles(marriottPoints, rule) >= targetMiles) return marriottPoints;
  }
  return Math.ceil(targetMiles * Number(rule.ratio || 3));
}

function awardInputs() {
  const milesPerSeat = Number($("#awardMiles").value || 0);
  const seats = Math.max(1, Number($("#awardSeats").value || 1));
  return {
    tripName: $("#awardTripName").value.trim() || "未命名旅程",
    program: $("#awardProgram").value,
    milesPerSeat,
    seats,
    totalMiles: milesPerSeat * seats,
    taxes: awardTaxInTwd(),
    cashValue: Number($("#awardCashValue").value || 0),
    oneWalletPrice: Number($("#oneWalletPrice").value || 0),
    oneWalletPoints: Number($("#oneWalletPoints").value || 1),
    oneWalletFeePct: Number($("#oneWalletFeePct").value || 0),
    oneWalletRatio: Number($("#oneWalletToMileRatio").value || 0),
    promoMarriottCost: Number($("#promoMarriottCost").value || 0),
    bonusMode: $("#marriottBonusMode").value,
    enabledSources: enabledCostSources(),
  };
}

function enabledCostSources() {
  const filters = $$(".source-filter");
  if (!filters.length) return new Set(["pingan", "official", "manual"]);
  return new Set(filters.filter(input => input.checked).map(input => input.dataset.source));
}

function awardRoutes(input) {
  const routes = [];
  const account = selectedAwardAccount();

  if (input.enabledSources.has("manual") && account?.category === "airline" && Number(account.costPerPoint || 0) > 0) {
    const mileageCost = input.totalMiles * Number(account.costPerPoint || 0);
    routes.push({
      title: `直接使用帳戶內 ${account.program}`,
      sourceType: "manual",
      totalCost: mileageCost + input.taxes,
      mileageCost,
      taxes: input.taxes,
      unitCost: input.totalMiles ? mileageCost / input.totalMiles : 0,
      detail: `${points(input.totalMiles)} 航空哩 × ${unitMoney(account.costPerPoint)}。目前餘額 ${points(account.balance)} 哩。`,
      warning: account.balance < input.totalMiles ? `餘額不足，還缺 ${points(input.totalMiles - account.balance)} 哩` : "",
    });
  }

  const marriottAccount = accountForProgram("Marriott");
  const transferRule = airlineRule(input.program, input.bonusMode);
  if (
    input.enabledSources.has("manual") &&
    transferRule?.category === "airline" &&
    marriottAccount &&
    Number(marriottAccount.costPerPoint || 0) > 0
  ) {
    const neededMarriott = marriottNeededForMiles(input.totalMiles, transferRule);
    const outputMiles = transferredMiles(neededMarriott, transferRule);
    const mileageCost = neededMarriott * Number(marriottAccount.costPerPoint || 0);
    routes.push({
      title: `帳戶內萬豪中轉 → ${input.program}`,
      sourceType: "manual",
      totalCost: mileageCost + input.taxes,
      mileageCost,
      taxes: input.taxes,
      unitCost: input.totalMiles ? mileageCost / input.totalMiles : 0,
      detail: `航空哩需求 ${points(input.totalMiles)}，需 Marriott ${points(neededMarriott)} 點，約可轉 ${points(outputMiles)} 哩；用你的 Marriott 成本 ${unitMoney(marriottAccount.costPerPoint)} / 點換算。`,
      warning: marriottAccount.balance < neededMarriott ? `Marriott 餘額不足，還缺 ${points(neededMarriott - marriottAccount.balance)} 點` : "",
    });
  }

  if (input.enabledSources.has("manual") && input.promoMarriottCost > 0) {
    const rule = airlineRule(input.program, input.bonusMode);
    if (rule?.category === "airline") {
      const neededMarriott = marriottNeededForMiles(input.totalMiles, rule);
      const outputMiles = transferredMiles(neededMarriott, rule);
      const mileageCost = neededMarriott * input.promoMarriottCost;
      routes.push({
        title: `壹錢包活動 → 萬豪中轉 → ${input.program}`,
        sourceType: "manual",
        totalCost: mileageCost + input.taxes,
        mileageCost,
        taxes: input.taxes,
        unitCost: input.totalMiles ? mileageCost / input.totalMiles : 0,
        detail: `萬豪只作為中轉點：航空哩需求 ${points(input.totalMiles)}，需 Marriott ${points(neededMarriott)} 點，約可轉 ${points(outputMiles)} 哩。${Number(rule.bonusMiles || 0) > 0 ? "已套用 60k +5k bonus。" : "未套用 60k bonus。"}`,
      });
    }
  }

  const cnyRate = Number(state.rates.CNY || 4.35);
  const oneWalletFeeRate = input.oneWalletFeePct / 100;
  const oneWalletPointCost = input.oneWalletPoints ? (input.oneWalletPrice * cnyRate * (1 + oneWalletFeeRate)) / input.oneWalletPoints : 0;
  const autoPinganRoutes = input.enabledSources.has("pingan") ? pinganRoutes(input, oneWalletPointCost) : [];
  autoPinganRoutes.forEach(route => routes.push(route));
  officialCostRoutes(input).forEach(route => routes.push(route));
  if (input.enabledSources.has("pingan") && input.oneWalletPrice > 0 && input.oneWalletPoints > 0 && input.oneWalletRatio > 0) {
    const neededOneWalletPoints = input.totalMiles / input.oneWalletRatio;
    const mileageCost = neededOneWalletPoints * oneWalletPointCost;
    routes.push({
      title: `壹錢包直接換 ${input.program}`,
      sourceType: "pingan",
      totalCost: mileageCost + input.taxes,
      mileageCost,
      taxes: input.taxes,
      unitCost: input.totalMiles ? mileageCost / input.totalMiles : 0,
      detail: `壹錢包基礎成本 ${unitMoney(oneWalletPointCost)} / 點；需要約 ${points(neededOneWalletPoints)} 壹錢包點。`,
    });
  } else if (input.enabledSources.has("pingan") && !autoPinganRoutes.length) {
    routes.push({
      title: "手動壹錢包路徑待補比例",
      totalCost: null,
      mileageCost: 0,
      taxes: input.taxes,
      unitCost: 0,
      detail: `目前基礎成本約 ${unitMoney(oneWalletPointCost)} / 壹錢包點。若平安表格沒有此計畫，可手動填入比例加入排序。`,
      warning: "等待匯入或手動輸入兌換比例。",
    });
  }

  return routes.sort((a, b) => {
    if (a.totalCost === null) return 1;
    if (b.totalCost === null) return -1;
    return a.totalCost - b.totalCost;
  });
}

function pinganRoutes(input, currentPointCost) {
  const rules = state.pinganRules.programs || [];
  const matched = rules.filter(rule => rule.program === input.program && Number(rule.wanlitongPerMile || 0) > 0);
  if (!matched.length || !input.totalMiles) return [];
  return matched.map(rule => {
    const unitCost = directWanlitongCost(rule);
    const mileageCost = input.totalMiles * unitCost;
    const source = rule.formulaType === "marriott_transfer" ? "平安萬里通 → 萬豪中轉 → 航空" : "平安萬里通表格";
    const variant = rule.variant ? `｜${rule.variant}` : "";
    return {
      title: `${source} → ${input.program}${variant}`,
      program: rule.program,
      sourceType: "pingan",
      totalCost: mileageCost + input.taxes,
      mileageCost,
      taxes: input.taxes,
      unitCost,
      detail: `依平安表格成本換算，並用目前 RMB 價格、CNY 匯率與 ${input.oneWalletFeePct}% 手續費等比例更新。`,
    };
  });
}

function officialCostRoutes(input) {
  if (!input.enabledSources.has("official")) return [];
  return (state.officialCosts.programs || [])
    .filter(rule => rule.program === input.program && Number(rule.costPerMile || 0) > 0)
    .map(rule => {
      const unitCost = Number(rule.costPerMile || 0);
      const mileageCost = input.totalMiles * unitCost;
      return {
        title: `官網/特賣購買 → ${rule.program}`,
        program: rule.program,
        sourceType: "official",
        totalCost: mileageCost + input.taxes,
        mileageCost,
        taxes: input.taxes,
        unitCost,
        detail: `${rule.vendor || "官方/TripPlus"}｜加贈 ${Number(rule.bonusPercent || 0).toFixed(0)}%${rule.endsAt ? `｜期限 ${rule.endsAt}` : ""}${rule.note ? `｜${rule.note}` : ""}`,
      };
    });
}

function pinganCompareRows(input) {
  const comparablePrograms = new Set([...airlinePrograms]);
  if (input.program === "Marriott") comparablePrograms.add("Marriott");
  const bestByProgram = new Map();
  if (input.enabledSources.has("pingan")) (state.pinganRules.programs || []).forEach(rule => {
    const unitCost = directWanlitongCost(rule);
    if (!rule.program || !unitCost || !comparablePrograms.has(rule.program)) return;
    const mileageCost = unitCost * input.totalMiles;
    const row = {
      program: rule.program,
      route: rule.formulaType === "marriott_transfer" ? "萬里通→萬豪中轉→航空" : "萬里通直轉",
      variant: rule.variant || "一般",
      unitCost,
      mileageCost,
      totalCost: mileageCost + input.taxes,
    };
    const existing = bestByProgram.get(rule.program);
    if (!existing || row.totalCost < existing.totalCost) bestByProgram.set(rule.program, row);
  });
  if (input.enabledSources.has("official")) (state.officialCosts.programs || []).forEach(rule => {
    const unitCost = Number(rule.costPerMile || 0);
    if (!rule.program || !unitCost || !comparablePrograms.has(rule.program)) return;
    const mileageCost = unitCost * input.totalMiles;
    const row = {
      program: rule.program,
      route: "官網/特賣購買",
      variant: rule.vendor || "官方",
      unitCost,
      mileageCost,
      totalCost: mileageCost + input.taxes,
    };
    const existing = bestByProgram.get(rule.program);
    if (!existing || row.totalCost < existing.totalCost) bestByProgram.set(rule.program, row);
  });
  return Array.from(bestByProgram.values()).sort((a, b) => a.totalCost - b.totalCost);
}

function renderAwardCost() {
  const result = $("#awardCostResult");
  const compare = $("#programCompareResult");
  if (!result) return;
  const input = awardInputs();
  result.replaceChildren();
  if (compare) compare.replaceChildren();
  if (!input.program || !input.totalMiles) {
    result.textContent = "請輸入查到的計畫、單人里程與張數。";
    return;
  }
  const routes = awardRoutes(input);
  const bestCost = routes.find(route => route.totalCost !== null)?.totalCost || 0;
  routes.forEach((route, index) => {
    const savings = input.cashValue && route.totalCost !== null ? input.cashValue - route.totalCost : 0;
    const card = document.createElement("article");
    card.className = `route-card ${index === 0 && route.totalCost !== null ? "best" : ""}`;
    card.innerHTML = `
      <div class="route-heading">
        <strong>${index === 0 && route.totalCost !== null ? "最佳路徑｜" : ""}${route.title}</strong>
        <span>${route.totalCost === null ? "待補規則" : money(route.totalCost)}</span>
      </div>
      <div class="route-meta">
        <span>里程需求 ${points(input.totalMiles)}</span>
        <span>里程成本 ${route.totalCost === null ? "待補" : money(route.mileageCost)}</span>
        <span>稅金 ${money(route.taxes)}</span>
        <span>每哩成本 ${route.unitCost ? `TWD ${route.unitCost.toFixed(2)}` : "待補"}</span>
      </div>
      <p>${route.detail}</p>
      ${input.cashValue && route.totalCost !== null ? `<p>現金票價 ${money(input.cashValue)}，${savings >= 0 ? `約省 ${money(savings)}` : `比現金多 ${money(Math.abs(savings))}`}。</p>` : ""}
      ${route.totalCost !== null && bestCost && route.totalCost > bestCost ? `<p>比目前最佳路徑多 ${money(route.totalCost - bestCost)}。</p>` : ""}
      ${route.warning ? `<p class="route-warning">${route.warning}</p>` : ""}
    `;
    result.append(card);
  });
  renderProgramCompare(input);
}

function renderProgramCompare(input) {
  const panel = $("#programCompareResult");
  if (!panel) return;
  const rows = pinganCompareRows(input).slice(0, 12);
  if (!rows.length) return;
  panel.innerHTML = `
    <div class="section-heading compact-heading">
      <h2>其他計畫同里程比較</h2>
      <span>${points(input.totalMiles)} 哩 + 稅金 ${money(input.taxes)}</span>
    </div>
    <div class="compare-grid">
      ${rows.map((row, index) => `
        <article class="compare-row ${row.program === input.program ? "selected" : ""}">
          <strong>${index + 1}. ${escapeHtml(row.program)}</strong>
          <span>${escapeHtml(row.route)}｜${escapeHtml(row.variant)}</span>
          <span>每哩 TWD ${row.unitCost.toFixed(2)}</span>
          <b>${money(row.totalCost)}</b>
        </article>
      `).join("")}
    </div>
  `;
}

function saveAwardCost() {
  const input = awardInputs();
  const best = awardRoutes(input).find(route => route.totalCost !== null);
  currentAwardCosts().unshift({
    createdAt: new Date().toISOString(),
    tripName: input.tripName,
    program: input.program,
    summary: best
      ? `${points(input.totalMiles)} 哩 / ${input.seats} 張，最佳 ${best.title}，總成本 ${money(best.totalCost)}`
      : `${points(input.totalMiles)} 哩 / ${input.seats} 張，等待補兌換比例`,
  });
  saveData();
  renderAwardCostHistory();
}

function renderAwardCostHistory() {
  const list = $("#awardCostHistory");
  if (!list) return;
  list.replaceChildren();
  currentAwardCosts().slice(0, 8).forEach(item => {
    const row = document.createElement("article");
    row.className = "quote-item";
    row.innerHTML = `<strong>${item.tripName}｜${item.program}</strong><br>${item.summary}`;
    list.append(row);
  });
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  }[char]));
}

function defaultDashboardVisible(rule) {
  if (typeof rule.showOnDashboard === "boolean") return rule.showOnDashboard;
  return rule.program === "Asia Miles" || rule.program === "Marriott";
}

function wanlitongAssumptions() {
  const assumptions = state.pinganRules.assumptions || {};
  return {
    rmbCost: Number(assumptions.walletFaceValueRmb ?? 950),
    points: Number(assumptions.walletPoints ?? 500000),
    cnyRate: Number(assumptions.cnyRateOverride || state.rates.CNY || assumptions.cnyRateFromSheet || 4.35),
    globalBonus: Number(assumptions.globalBonusMultiplier || 1),
  };
}

function wanlitongPointCost() {
  const input = wanlitongAssumptions();
  return wanlitongPointCostFrom(input);
}

function wanlitongPointCostFrom(input) {
  if (!input.points || !input.globalBonus) return 0;
  return (Number(input.rmbCost || 0) * Number(input.cnyRate || 0)) / (Number(input.points || 1) * Number(input.globalBonus || 1));
}

function directWanlitongCost(rule, pointCost = wanlitongPointCost()) {
  const perMile = Number(rule.wanlitongPerMile || 0);
  const itemBonus = Number(rule.bonusMultiplier || 1);
  if (!perMile || !itemBonus) return 0;
  return (pointCost * perMile) / itemBonus;
}

function marriottWanlitongCost() {
  const candidates = (state.pinganRules.programs || [])
    .filter(rule => rule.program === "Marriott" && Number(rule.wanlitongPerMile || 0) > 0)
    .map(rule => directWanlitongCost(rule))
    .filter(Boolean);
  return candidates.length ? Math.min(...candidates) : 0;
}

function defaultMarriottRules() {
  const preferred = [
    "Alaska",
    "Air Canada Aeroplan",
    "United",
    "Asia Miles",
    "British Airways Avios",
    "Qatar Avios",
    "Finnair Avios",
    "JAL",
    "ANA",
    "EVA Air",
    "China Airlines",
    "Flying Blue",
    "LifeMiles",
  ];
  return preferred.map(program => ({
    program,
    category: "airline",
    milesPer60k: program === "United" ? 30000 : (program === "LifeMiles" ? 20000 : 25000),
    showOnDashboard: ["Alaska", "Air Canada Aeroplan", "Asia Miles"].includes(program),
  }));
}

function marriottRules() {
  const existing = state.data.marriottRules || [];
  if (existing.length) return existing;
  state.data.marriottRules = defaultMarriottRules();
  return state.data.marriottRules;
}

function marriottCostPerMile(rule) {
  const baseCost = selectedMarriottBaseCost();
  const output = Number(rule.milesPer60k || 0);
  return baseCost && output ? (60000 * baseCost) / output : 0;
}

function selectedMarriottBaseCost() {
  const settings = state.data.marriottCostSettings || {};
  if (settings.source === "manual") return Number(settings.manualCost || 0);
  if (settings.source === "account") return Number(accountForProgram("Marriott")?.costPerPoint || 0);
  return marriottWanlitongCost();
}

function marriottBaseCostSourceLabel() {
  const settings = state.data.marriottCostSettings || {};
  if (settings.source === "manual") return "手動輸入 Marriott 成本";
  if (settings.source === "account") return "使用帳戶內 Marriott 成本";
  return "自動抓第二頁「萬里通 → 萬豪」最低成本";
}

function renderCostLine(item) {
  const row = document.createElement("article");
  row.className = "cost-line";
  row.innerHTML = `
    <strong>${escapeHtml(item.program)}</strong>
    <span>${escapeHtml(item.route)}</span>
    <b>TWD ${Number(item.cost || 0).toFixed(2)}</b>
  `;
  return row;
}

function renderPinganDashboard() {
  const marriottRows = $("#pinganMarriottRows");
  const directRows = $("#pinganDirectRows");
  if (!marriottRows || !directRows) return;
  marriottRows.replaceChildren();
  directRows.replaceChildren();
  marriottRules()
    .filter(rule => rule.showOnDashboard)
    .map(rule => ({ program: rule.program, route: `60k Marriott → ${points(rule.milesPer60k || 0)} 哩`, cost: marriottCostPerMile(rule) }))
    .sort((a, b) => a.cost - b.cost)
    .forEach(item => marriottRows.append(renderCostLine(item)));
  (state.pinganRules.programs || [])
    .filter(rule => defaultDashboardVisible(rule) && rule.formulaType !== "marriott_transfer")
    .map(rule => ({ program: rule.program, route: `萬里通直轉｜${rule.rawName || "-"}`, cost: directWanlitongCost(rule) }))
    .filter(item => item.cost > 0)
    .sort((a, b) => a.cost - b.cost)
    .forEach(item => directRows.append(renderCostLine(item)));
  if (!marriottRows.children.length) marriottRows.textContent = "尚未勾選任何萬豪轉點項目。";
  if (!directRows.children.length) directRows.textContent = "尚未勾選任何萬里通直轉項目。";
}

function renderPinganEditor() {
  const body = $("#pinganRulesBody");
  if (!body) return;
  const assumptions = state.pinganRules.assumptions || {};
  $("#pinganFaceValue").value = assumptions.walletFaceValueRmb ?? 950;
  $("#pinganWalletPoints").value = assumptions.walletPoints ?? 500000;
  $("#pinganCnyRate").value = Number(assumptions.cnyRateOverride || state.rates.CNY || assumptions.cnyRateFromSheet || 4.35).toFixed(4);
  const unitCost = wanlitongPointCost();
  $("#pinganPointCost").textContent = `每 1 萬里通積分 TWD ${unitCost.toFixed(6)}`;
  $("#pinganPointCostDetail").textContent = `${points(wanlitongAssumptions().points)} 積分 / RMB ${wanlitongAssumptions().rmbCost} / CNY ${wanlitongAssumptions().cnyRate.toFixed(4)}`;
  body.replaceChildren();
  (state.pinganRules.programs || []).forEach((rule, index) => {
    const calculatedCost = directWanlitongCost(rule);
    const row = document.createElement("tr");
    row.className = "pingan-rule-row";
    row.dataset.index = String(index);
    row.innerHTML = `
      <td><input class="mini-check" data-field="showOnDashboard" type="checkbox"${defaultDashboardVisible(rule) ? " checked" : ""} /></td>
      <td><input class="mini-input" data-field="sourceRow" inputmode="numeric" type="number" min="1" step="1" value="${Number(rule.sourceRow || index + 1)}" /></td>
      <td><input data-field="programCombined" title="${escapeHtml(`${rule.program || ""} / ${rule.rawName || ""}`)}" value="${escapeHtml(`${rule.program || ""} / ${rule.rawName || ""}`)}" /></td>
      <td><input class="mini-input" data-field="bonusMultiplier" inputmode="decimal" type="number" min="0.01" step="0.01" value="${Number(rule.bonusMultiplier || 1).toFixed(2)}" /></td>
      <td><input class="mini-input" data-field="wanlitongPerMile" inputmode="numeric" type="number" min="0" step="1" value="${Math.round(Number(rule.wanlitongPerMile || 0))}" /></td>
      <td><span class="readonly-cost" data-calculated-cost>TWD ${calculatedCost.toFixed(2)}</span></td>
      <td class="action-cell">
        <button class="secondary-button small-button" data-toggle-formula="${index}" type="button">公式</button>
        <button class="danger-button small-button icon-only" data-delete-pingan="${index}" type="button" title="刪除">X</button>
      </td>
    `;
    body.append(row);
    const formulaRow = document.createElement("tr");
    formulaRow.className = "formula-row";
    formulaRow.hidden = true;
    formulaRow.dataset.formulaIndex = String(index);
    formulaRow.innerHTML = `
      <td colspan="7">
        <label>Excel 公式
          <input class="formula-input" data-formula-field="${index}" title="${escapeHtml(rule.formula || "")}" value="${escapeHtml(rule.formula || "")}" />
        </label>
      </td>
    `;
    body.append(formulaRow);
  });
  $("#pinganTableStatus").textContent = `目前 ${state.pinganRules.programs?.length || 0} 條規則。`;
}

function updatePinganCalculatedCosts() {
  const unitCost = wanlitongPointCost();
  const assumptions = wanlitongAssumptions();
  $("#pinganPointCost").textContent = `每 1 萬里通積分 TWD ${unitCost.toFixed(6)}`;
  $("#pinganPointCostDetail").textContent = `${points(assumptions.points)} 積分 / RMB ${assumptions.rmbCost} / CNY ${assumptions.cnyRate.toFixed(4)}`;
  $$("#pinganRulesBody tr.pingan-rule-row").forEach((row, index) => {
    const rule = state.pinganRules.programs?.[index];
    const costNode = row.querySelector("[data-calculated-cost]");
    if (rule && costNode) {
      costNode.textContent = `TWD ${directWanlitongCost(rule, unitCost).toFixed(2)}`;
    }
  });
}

function collectPinganRules() {
  const assumptions = {
    ...(state.pinganRules.assumptions || {}),
    walletFaceValueRmb: Number($("#pinganFaceValue").value || 0),
    walletPoints: Number($("#pinganWalletPoints").value || 1),
    cnyRateOverride: Number($("#pinganCnyRate").value || 0),
    globalBonusMultiplier: Number(state.pinganRules.assumptions?.globalBonusMultiplier || 1),
  };
  const currentPointCost = wanlitongPointCostFrom({
    rmbCost: assumptions.walletFaceValueRmb,
    points: assumptions.walletPoints,
    cnyRate: assumptions.cnyRateOverride,
    globalBonus: assumptions.globalBonusMultiplier,
  });
  assumptions.wanlitongPointCostWithFeesCached = currentPointCost;
  const programs = $$("#pinganRulesBody tr.pingan-rule-row").map((row, index) => {
    const get = field => row.querySelector(`[data-field="${field}"]`)?.value?.trim() || "";
    const checked = field => Boolean(row.querySelector(`[data-field="${field}"]`)?.checked);
    const existing = state.pinganRules.programs?.[index] || {};
    const formula = $(`[data-formula-field="${index}"]`)?.value?.trim() || existing.formula || "";
    const combined = get("programCombined");
    const [programPart, ...rawParts] = combined.split("/");
    return {
      showOnDashboard: checked("showOnDashboard"),
      sourceRow: Number(get("sourceRow") || existing.sourceRow || index + 1),
      rawName: rawParts.join("/").trim() || existing.rawName || "",
      program: programPart.trim() || existing.program || "",
      formulaType: existing.formulaType || "direct",
      wanlitongPerMile: Number(get("wanlitongPerMile") || 0),
      bonusMultiplier: Number(get("bonusMultiplier") || 1),
      costPerMileWithFeesCached: directWanlitongCost({ wanlitongPerMile: Number(get("wanlitongPerMile") || 0), bonusMultiplier: Number(get("bonusMultiplier") || 1) }, currentPointCost),
      costPerMileWithoutFeesCached: directWanlitongCost({ wanlitongPerMile: Number(get("wanlitongPerMile") || 0), bonusMultiplier: Number(get("bonusMultiplier") || 1) }, currentPointCost),
      formula,
      variant: get("variant"),
    };
  }).filter(rule => rule.program);
  return {
    ...state.pinganRules,
    updatedAt: new Date().toISOString(),
    assumptions,
    programs,
  };
}

function addPinganRule() {
  if (!state.pinganRules.programs) state.pinganRules.programs = [];
  state.pinganRules.programs.push({
    sourceRow: state.pinganRules.programs.length + 1,
    rawName: "",
    program: "Alaska",
    formulaType: "direct",
    wanlitongPerMile: 0,
    bonusMultiplier: 1,
    costPerMileWithFeesCached: 0,
    costPerMileWithoutFeesCached: 0,
    formula: "手動新增",
    variant: "",
    showOnDashboard: true,
  });
  renderPinganEditor();
  renderPinganDashboard();
}

function renderMarriottRules() {
  const body = $("#marriottRulesBody");
  if (!body) return;
  const settings = state.data.marriottCostSettings || {};
  $("#marriottCostSource").value = settings.source || "wanlitong";
  $("#manualMarriottCost").value = Number(settings.manualCost || 0).toFixed(4);
  const baseCost = selectedMarriottBaseCost();
  $("#marriottBaseCost").textContent = `萬豪成本 TWD ${baseCost.toFixed(2)} / 點`;
  $("#marriottBaseCostSource").textContent = marriottBaseCostSourceLabel();
  body.replaceChildren();
  marriottRules().forEach((rule, index) => {
    const row = document.createElement("tr");
    row.dataset.index = String(index);
    row.innerHTML = `
      <td><input class="mini-check" data-field="showOnDashboard" type="checkbox"${rule.showOnDashboard ? " checked" : ""} /></td>
      <td><input data-field="program" value="${escapeHtml(rule.program || "")}" /></td>
      <td>
        <select data-field="category">
          <option value="airline"${rule.category === "airline" ? " selected" : ""}>航空</option>
          <option value="hotel"${rule.category === "hotel" ? " selected" : ""}>飯店</option>
        </select>
      </td>
      <td><input class="mini-input" data-field="milesPer60k" inputmode="numeric" type="number" min="0" step="1000" value="${Number(rule.milesPer60k || 0)}" /></td>
      <td><span class="readonly-cost" data-marriott-calculated-cost>TWD ${marriottCostPerMile(rule).toFixed(2)}</span></td>
    `;
    body.append(row);
  });
  $("#marriottRulesStatus").textContent = `目前 ${marriottRules().length} 條萬豪轉點設定；以 60,000 Marriott 點可換多少哩為基準。`;
}

function updateMarriottCalculatedCosts() {
  const baseCost = selectedMarriottBaseCost();
  $("#marriottBaseCost").textContent = `萬豪成本 TWD ${baseCost.toFixed(2)} / 點`;
  $("#marriottBaseCostSource").textContent = marriottBaseCostSourceLabel();
  $$("#marriottRulesBody tr").forEach((row, index) => {
    const rule = marriottRules()[index];
    const costNode = row.querySelector("[data-marriott-calculated-cost]");
    if (rule && costNode) {
      costNode.textContent = `TWD ${marriottCostPerMile(rule).toFixed(2)}`;
    }
  });
}

function refreshPinganDerivedCosts() {
  updatePinganCalculatedCosts();
  updateMarriottCalculatedCosts();
  renderPinganDashboard();
  renderAwardCost();
}

function collectMarriottRules() {
  return $$("#marriottRulesBody tr").map(row => {
    const get = field => row.querySelector(`[data-field="${field}"]`)?.value?.trim() || "";
    const checked = field => Boolean(row.querySelector(`[data-field="${field}"]`)?.checked);
    return {
      showOnDashboard: checked("showOnDashboard"),
      program: get("program"),
      category: get("category") || "airline",
      milesPer60k: Number(get("milesPer60k") || 0),
    };
  }).filter(rule => rule.program);
}

function collectMarriottCostSettings() {
  return {
    source: $("#marriottCostSource")?.value || "wanlitong",
    manualCost: Number($("#manualMarriottCost")?.value || 0),
  };
}

function setPinganDashboardChecks(checked) {
  $$('#pinganRulesBody [data-field="showOnDashboard"]').forEach(input => {
    input.checked = checked;
  });
  state.pinganRules = collectPinganRules();
  renderPinganDashboard();
  schedulePinganSave();
}

function selectedPinganKeys() {
  return $$("#pinganRulesBody tr.pingan-rule-row")
    .map((row, index) => ({ row, rule: state.pinganRules.programs?.[index] }))
    .filter(item => item.row.querySelector('[data-field="showOnDashboard"]')?.checked)
    .map(item => `${item.rule?.sourceRow || ""}|${item.rule?.program || ""}|${item.rule?.rawName || ""}`);
}

function savePinganPreset(slot) {
  state.data.pinganDisplayPresets ||= {};
  state.data.pinganDisplayPresets[String(slot)] = selectedPinganKeys();
  saveData();
  $("#pinganTableStatus").textContent = `已記憶勾選 ${slot}。`;
}

function applyPinganPreset(slot) {
  const keys = new Set(state.data.pinganDisplayPresets?.[String(slot)] || []);
  if (!keys.size) {
    $("#pinganTableStatus").textContent = `記憶 ${slot} 還沒有內容。`;
    return;
  }
  $$("#pinganRulesBody tr.pingan-rule-row").forEach((row, index) => {
    const rule = state.pinganRules.programs?.[index] || {};
    const key = `${rule.sourceRow || ""}|${rule.program || ""}|${rule.rawName || ""}`;
    const checkbox = row.querySelector('[data-field="showOnDashboard"]');
    if (checkbox) checkbox.checked = keys.has(key);
  });
  state.pinganRules = collectPinganRules();
  renderPinganDashboard();
  schedulePinganSave();
  $("#pinganTableStatus").textContent = `已套用記憶 ${slot}。`;
}

async function savePinganRules() {
  state.pinganRules = collectPinganRules();
  state.data.marriottRules = collectMarriottRules();
  state.data.marriottCostSettings = collectMarriottCostSettings();
  $("#pinganTableStatus").textContent = "正在儲存平安表格...";
  try {
    const response = await fetch("/api/pingan-rules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.pinganRules),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    $("#pinganTableStatus").textContent = `已儲存 ${state.pinganRules.programs.length} 條規則。`;
    saveData();
    renderAwardCost();
    renderPinganDashboard();
    renderMarriottRules();
  } catch (error) {
    $("#pinganTableStatus").textContent = `儲存失敗：${error.message}`;
  }
}

function renderOfficialCosts() {
  const body = $("#officialCostsBody");
  if (!body) return;
  body.replaceChildren();
  (state.officialCosts.programs || []).forEach((rule, index) => {
    const row = document.createElement("tr");
    row.dataset.index = String(index);
    row.dataset.existingNote = rule.note || "";
    row.innerHTML = `
      <td><input data-field="program" value="${escapeHtml(rule.program || "")}" /></td>
      <td><input data-field="vendor" value="${escapeHtml(rule.vendor || "")}" placeholder="官方/TripPlus" /></td>
      <td><input data-field="costPerMile" inputmode="decimal" type="number" min="0" step="0.01" value="${Number(rule.costPerMile || 0).toFixed(2)}" /></td>
      <td><input data-field="bonusPercent" inputmode="decimal" type="number" min="0" step="1" value="${Number(rule.bonusPercent || 0).toFixed(0)}" /></td>
      <td><input data-field="endsAt" type="date" value="${escapeHtml(rule.endsAt || "")}" /></td>
      <td><button class="danger-button small-button" data-delete-official="${index}" type="button">刪除</button></td>
    `;
    body.append(row);
  });
  $("#officialCostStatus").textContent = `目前 ${state.officialCosts.programs?.length || 0} 條官網/特賣成本。`;
}

function collectOfficialCosts() {
  const programs = $$("#officialCostsBody tr").map(row => {
    const get = field => row.querySelector(`[data-field="${field}"]`)?.value?.trim() || "";
    return {
      program: get("program"),
      vendor: get("vendor"),
      costPerMile: Number(get("costPerMile") || 0),
      bonusPercent: Number(get("bonusPercent") || 0),
      endsAt: get("endsAt"),
      note: row.dataset.existingNote || "",
    };
  }).filter(rule => rule.program);
  return {
    ...state.officialCosts,
    updatedAt: new Date().toISOString(),
    programs,
  };
}

function addOfficialCost() {
  if (!state.officialCosts.programs) state.officialCosts.programs = [];
  state.officialCosts.programs.push({
    program: "Alaska",
    vendor: "官方/TripPlus",
    costPerMile: 0,
    bonusPercent: 0,
    endsAt: "",
    note: "",
  });
  renderOfficialCosts();
}

async function saveOfficialCosts() {
  state.officialCosts = collectOfficialCosts();
  $("#officialCostStatus").textContent = "正在儲存官網成本...";
  try {
    const response = await fetch("/api/official-costs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.officialCosts),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    $("#officialCostStatus").textContent = `已儲存 ${state.officialCosts.programs.length} 條官網成本。`;
    renderAwardCost();
  } catch (error) {
    $("#officialCostStatus").textContent = `儲存失敗：${error.message}`;
  }
}

function scheduleOfficialSave() {
  clearTimeout(officialSaveTimer);
  officialSaveTimer = setTimeout(saveOfficialCosts, 800);
  $("#officialCostStatus").textContent = "已變更，準備自動儲存...";
}

async function refreshTripplus() {
  $("#officialCostStatus").textContent = "正在嘗試刷新 TripPlus...";
  try {
    const response = await fetch("/api/tripplus-refresh", { cache: "no-store" });
    const payload = await response.json();
    if (payload.programs) state.officialCosts.programs = payload.programs;
    $("#officialCostStatus").textContent = payload.message || (payload.ok ? "TripPlus 已刷新。" : "TripPlus 無可用更新。");
    renderOfficialCosts();
    renderAwardCost();
  } catch (error) {
    $("#officialCostStatus").textContent = `刷新失敗：${error.message}`;
  }
}

async function loadOfficialCosts() {
  try {
    const response = await fetch("/api/official-costs", { cache: "no-store" });
    state.officialCosts = await response.json();
  } catch {
    state.officialCosts = { programs: [], source: "manual" };
  }
  renderOfficialCosts();
  renderAwardCost();
}

function cabinField(cabin) {
  return { economy: "Y", premium: "W", business: "J", first: "F", Y: "Y", W: "W", J: "J", F: "F" }[cabin] || "Y";
}

function seatTaxValue(item, code) {
  const raw = Number(item[`${code}TotalTaxesRaw`] || item[`${code}TotalTaxes`] || item.TaxesRaw || item.Taxes || item.tax || 0);
  return raw > 1000 ? raw / 100 : raw;
}

function seatOptionFromItem(item, cabin) {
  const code = cabinField(cabin);
  return {
    date: item.Date || item.DepartureDate || item.date || "",
    miles: Number(item[`${code}MileageCost`] || item[`${code}MileageCostRaw`] || item.MileageCost || item.mileage || 0),
    tax: seatTaxValue(item, code),
    currency: item.TaxesCurrency || item.Currency || "USD",
    seats: Number(item[`${code}RemainingSeats`] || item[`${code}RemainingSeatsRaw`] || item.RemainingSeats || 0),
    airline: item[`${code}Airlines`] || item[`${code}AirlinesRaw`] || item.Airline || item.Airlines || item.Carriers || "",
    source: item.Source || "",
  };
}

async function searchSeatsAero() {
  const params = new URLSearchParams({
    origin: $("#seatOrigin").value.trim(),
    destination: $("#seatDestination").value.trim(),
    source: $("#seatSource").value,
    startDate: $("#seatStartDate").value,
    endDate: $("#seatEndDate").value,
    cabins: $("#seatCabins").value,
    take: "20",
  });
  $("#seatSearchStatus").textContent = "正在查 Seats.aero...";
  $("#seatSearchResults").replaceChildren();
  try {
    const response = await fetch(`/api/seataero-search?${params.toString()}`, { cache: "no-store" });
    const payload = await response.json();
    if (!payload.ok) throw new Error(payload.error || "Seats.aero 查詢失敗");
    const items = Array.isArray(payload.result) ? payload.result : (payload.result.data || payload.result.results || payload.result.Items || []);
    renderSeatSearchResults(items, $("#seatCabins").value);
    $("#seatSearchStatus").textContent = `查到 ${items.length} 筆。`;
  } catch (error) {
    $("#seatSearchStatus").textContent = `查詢失敗：${error.message}`;
  }
}

function renderSeatSearchResults(items, cabin) {
  const list = $("#seatSearchResults");
  list.replaceChildren();
  items.slice(0, 10).forEach(item => {
    const option = seatOptionFromItem(item, cabin);
    const row = document.createElement("article");
    row.className = "seat-result";
    row.innerHTML = `
      <strong>${escapeHtml(option.date || "日期未明")}｜${points(option.miles)} 哩</strong>
      <span>稅費 ${option.currency} ${option.tax ? option.tax.toFixed(2) : "0.00"}｜席位 ${option.seats || "-"}｜${escapeHtml(option.airline || "")}</span>
      <button class="secondary-button small-button" type="button">套用</button>
    `;
    row.querySelector("button").addEventListener("click", () => {
      const mappedProgram = sourceToProgram(option.source);
      if (mappedProgram && [...$("#awardProgram").options].some(item => item.value === mappedProgram)) {
        $("#awardProgram").value = mappedProgram;
      }
      if (option.miles) $("#awardMiles").value = option.miles;
      if (option.tax) $("#awardTax").value = option.tax.toFixed(2);
      if ([...$("#awardCurrency").options].some(item => item.value === option.currency)) {
        $("#awardCurrency").value = option.currency;
      }
      renderAwardCost();
    });
    list.append(row);
  });
}

function schedulePinganSave() {
  clearTimeout(pinganSaveTimer);
  pinganSaveTimer = setTimeout(savePinganRules, 800);
  $("#pinganTableStatus").textContent = "已變更，準備自動儲存...";
}

function renderTransferPrograms() {
  const select = $("#transferTarget");
  if (!select) return;
  const current = select.value;
  select.replaceChildren();
  const rules = state.transferRules.length
    ? state.transferRules
    : [...airlinePrograms.map(program => ({ program, category: "airline", ratio: 3, bonusThreshold: 60000, bonusMiles: program === "LifeMiles" ? 0 : 5000 })), ...hotelPrograms.map(program => ({ program, category: "hotel" }))];
  rules.forEach(rule => {
    const option = document.createElement("option");
    option.value = rule.program;
    option.textContent = `${rule.program} (${categoryLabel(rule.category)})`;
    select.append(option);
  });
  if (current && rules.some(rule => rule.program === current)) select.value = current;
}

function selectedTransferRule() {
  const selected = $("#transferTarget").value;
  return state.transferRules.find(rule => rule.program === selected) || null;
}

function selectedTransferAccount(program) {
  return currentAccounts().find(item => item.program === program) || null;
}

function transferredMiles(marriottPoints, rule) {
  if (!rule?.ratio) return 0;
  const baseMiles = Math.floor(marriottPoints / Number(rule.ratio || 3));
  const bonusBlocks = rule.bonusThreshold ? Math.floor(marriottPoints / rule.bonusThreshold) : 0;
  return baseMiles + bonusBlocks * Number(rule.bonusMiles || 0);
}

function renderTransfer() {
  const rule = selectedTransferRule();
  const result = $("#transferResult");
  if (!rule) {
    result.textContent = "轉點規則載入中。";
    return;
  }
  const marriottPoints = Number($("#marriottPoints").value || 0);
  const marriottCost = Number($("#marriottCost").value || 0);
  const pointsCost = marriottPoints * marriottCost;
  const taxes = transferTaxInTwd();
  const totalCost = pointsCost + taxes;
  const cashValue = Number($("#transferCashValue").value || 0);
  const savings = cashValue ? cashValue - totalCost : 0;

  if (rule.category === "airline") {
    const miles = transferredMiles(marriottPoints, rule);
    const unitCost = miles ? totalCost / miles : 0;
    const bonusText = Number(rule.bonusMiles || 0) > 0 ? `含 ${Math.floor(marriottPoints / rule.bonusThreshold) * rule.bonusMiles} bonus 哩` : "不含 60k bonus";
    result.innerHTML = `
      <span>Marriott ${points(marriottPoints)} 點 → ${rule.program}</span>
      <strong>約可換 ${points(miles)} 哩</strong>
      <span>實際成本 ${money(totalCost)}，每哩成本 TWD ${unitCost.toFixed(2)}</span>
      <span>Marriott 成本 ${money(pointsCost)} + 稅金 ${money(taxes)}｜${bonusText}</span>
      <span>${cashValue ? `相對現金價省 ${money(savings)}` : "填入現金價值後可估算是否划算"}</span>
    `;
    return;
  }

  const targetAccount = selectedTransferAccount(rule.program);
  const targetCost = Number(targetAccount?.costPerPoint || 0);
  const equivalentPoints = targetCost ? totalCost / targetCost : 0;
  result.innerHTML = `
    <span>Marriott ${points(marriottPoints)} 點 → ${rule.program} 成本比較</span>
    <strong>Marriott 成本 ${money(totalCost)}</strong>
    <span>${targetCost ? `以你設定的 ${rule.program} 成本，等值約 ${points(equivalentPoints)} 點` : `請先在 ${rule.program} 帳戶填每點成本，即可換算等值點數`}</span>
    <span>${cashValue ? `相對現金價省 ${money(savings)}` : "飯店計畫不是官方直接轉點，這裡只做預算比較"}</span>
  `;
}

function saveTransfer() {
  const rule = selectedTransferRule();
  if (!rule) return;
  const marriottPoints = Number($("#marriottPoints").value || 0);
  const totalCost = marriottPoints * Number($("#marriottCost").value || 0) + transferTaxInTwd();
  const output = rule.category === "airline"
    ? `${points(transferredMiles(marriottPoints, rule))} 哩`
    : "成本等值比較";
  currentTransfers().unshift({
    createdAt: new Date().toISOString(),
    program: rule.program,
    summary: `${points(marriottPoints)} Marriott 點 → ${output}，實際成本 ${money(totalCost)}`,
  });
  saveData();
  renderTransferHistory();
}

function renderTransferHistory() {
  const list = $("#transferHistory");
  if (!list) return;
  list.replaceChildren();
  currentTransfers().slice(0, 8).forEach(item => {
    const row = document.createElement("article");
    row.className = "quote-item";
    row.innerHTML = `<strong>${item.program}</strong><br>${item.summary}`;
    list.append(row);
  });
}

function renderQuoteHistory() {
  const list = $("#quoteHistory");
  list.replaceChildren();
  currentQuotes().slice(0, 8).forEach(item => {
    const row = document.createElement("article");
    row.className = "quote-item";
    row.innerHTML = `<strong>${item.program}</strong><br>${item.note || "未命名試算"}<br>${item.summary}`;
    list.append(row);
  });
}

function renderExpiry() {
  const list = $("#expiryList");
  list.replaceChildren();
  const sorted = currentAccounts()
    .filter(item => item.expiryDate)
    .sort((a, b) => a.expiryDate.localeCompare(b.expiryDate));
  const groups = [
    { title: "30 天內", items: sorted.filter(item => {
      const days = daysUntil(item.expiryDate);
      return days !== null && days >= 0 && days <= 30;
    }) },
    { title: "60 天內", items: sorted.filter(item => {
      const days = daysUntil(item.expiryDate);
      return days !== null && days > 30 && days <= 60;
    }) },
    { title: "其他到期日", items: sorted.filter(item => {
      const days = daysUntil(item.expiryDate);
      return days !== null && (days < 0 || days > 60);
    }) },
  ];
  const notifyItems = sorted.filter(item => {
    const days = daysUntil(item.expiryDate);
    return days !== null && days >= 0 && days <= 60;
  });
  if (notifyItems.length) {
    const subject = encodeURIComponent("Points Wallet 到期提醒");
    const body = encodeURIComponent(notifyItems.map(item => {
      const days = daysUntil(item.expiryDate);
      return `${item.program}: ${points(item.balance)} 點/哩，${item.expiryDate}，${days} 天後到期`;
    }).join("\n"));
    const notice = document.createElement("article");
    notice.className = "expiry-item expiry-notice";
    notice.innerHTML = `<strong>Email 提醒草稿</strong><br>60 天內共有 ${notifyItems.length} 筆到期。<br><a href="mailto:${expiryNotifyEmail}?subject=${subject}&body=${body}">寄到 ${expiryNotifyEmail}</a>`;
    list.append(notice);
  }
  groups.forEach(group => {
    if (!group.items.length) return;
    const heading = document.createElement("h3");
    heading.className = "expiry-group-heading";
    heading.textContent = group.title;
    list.append(heading);
    group.items.forEach(item => {
      const days = daysUntil(item.expiryDate);
      const row = document.createElement("article");
      row.className = `expiry-item ${days < 0 ? "expired" : days <= 60 ? "expiry-soon" : ""}`;
      row.innerHTML = `<strong>${item.program}</strong><br>${points(item.balance)} 點/哩｜${item.expiryDate}｜${days < 0 ? "已過期" : `${days} 天後到期`}`;
      list.append(row);
    });
  });
  if (!sorted.length) {
    list.textContent = "尚未填任何到期日。";
  }
}

function openAccountDialog(id = null) {
  state.editingId = id;
  const item = id ? currentAccounts().find(account => account.id === id) : account("hotel", "Marriott");
  $("#dialogTitle").textContent = id ? "編輯帳戶" : "新增帳戶";
  $("#accountId").value = id || "";
  $("#accountCategory").value = item.category;
  populateProgramSelect(item.category, item.program);
  $("#accountBalance").value = item.balance || 0;
  $("#accountCost").value = item.costPerPoint || 0;
  $("#accountExpiry").value = item.expiryDate || "";
  $("#deleteAccountBtn").style.visibility = id ? "visible" : "hidden";
  $("#accountDialog").showModal();
}

function addAccountInline() {
  currentAccounts().push(account("hotel", "Marriott"));
  saveData();
  render();
}

function updateAccountInline(row) {
  const id = row.dataset.id;
  const item = currentAccounts().find(account => account.id === id);
  if (!item) return;
  row.querySelectorAll(".account-input").forEach(input => {
    const field = input.dataset.field;
    item[field] = input.type === "number" ? Number(input.value || 0) : input.value;
  });
  if (row.querySelector('[data-field="category"]') === document.activeElement || !((item.category === "hotel" ? hotelPrograms : airlinePrograms).includes(item.program))) {
    item.program = item.category === "hotel" ? hotelPrograms[0] : airlinePrograms[0];
    populateInlineProgramSelect(row.querySelector(".account-program-select"), item.category, item.program);
  }
  scheduleSaveData();
  renderSummary();
  const totalCost = Number(item.balance || 0) * Number(item.costPerPoint || 0);
  row.querySelector(".cost").textContent = `加總成本 ${money(totalCost)}`;
  renderQuotePrograms();
  renderAwardPrograms();
  renderQuote();
  renderAwardCost();
  renderExpiry();
}

function deleteAccountById(id) {
  state.data.accounts[state.owner] = currentAccounts().filter(item => item.id !== id);
  saveData();
  render();
}

function populateProgramSelect(category, selected) {
  const select = $("#accountProgram");
  const programs = category === "hotel" ? hotelPrograms : airlinePrograms;
  select.replaceChildren();
  programs.forEach(program => {
    const option = document.createElement("option");
    option.value = program;
    option.textContent = program;
    select.append(option);
  });
  select.value = selected || programs[0];
}

function saveAccount() {
  const id = $("#accountId").value || createId();
  const existing = currentAccounts().find(account => account.id === id);
  const item = {
    id,
    category: $("#accountCategory").value,
    program: $("#accountProgram").value,
    balance: Number($("#accountBalance").value || 0),
    costPerPoint: Number($("#accountCost").value || 0),
    expiryDate: $("#accountExpiry").value,
    note: existing?.note || "",
  };
  const accounts = currentAccounts();
  const index = accounts.findIndex(account => account.id === id);
  if (index >= 0) accounts[index] = item;
  else accounts.push(item);
  saveData();
  render();
}

function deleteAccount() {
  const id = $("#accountId").value;
  state.data.accounts[state.owner] = currentAccounts().filter(item => item.id !== id);
  saveData();
  render();
  $("#accountDialog").close();
}

function saveQuote() {
  const account = selectedQuoteAccount();
  if (!account) return;
  const usedPoints = Number($("#quotePoints").value || 0);
  const totalCost = usedPoints * Number(account.costPerPoint || 0) + taxInTwd();
  const quote = {
    createdAt: new Date().toISOString(),
    program: account.program,
    note: $("#quoteNote").value.trim(),
    summary: `${points(usedPoints)} 點，實際成本 ${money(totalCost)}`,
  };
  state.data.quotes[state.owner].unshift(quote);
  saveData();
  renderQuoteHistory();
}

function exportJson() {
  const blob = new Blob([JSON.stringify(state.data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "points-wallet.json";
  link.click();
  URL.revokeObjectURL(url);
}

async function loadRates() {
  try {
    const response = await fetch("/api/rates", { cache: "no-store" });
    const data = await response.json();
    if (!data.rates) throw new Error("missing rates");
    state.rates = data.rates;
    state.rates.TWD = 1;
    $("#rateStatus").textContent = `匯率已更新 ${new Date().toLocaleString("zh-TW")}`;
  } catch {
    $("#rateStatus").textContent = "匯率使用離線預設值";
  }
  renderQuote();
  renderTransfer();
  renderAwardCost();
  renderPinganEditor();
  renderMarriottRules();
  renderPinganDashboard();
}

async function loadTransferRules() {
  try {
    const response = await fetch("/api/transfer-rules", { cache: "no-store" });
    const data = await response.json();
    state.transferRules = data.programs || [];
  } catch {
    state.transferRules = [];
  }
  renderTransferPrograms();
  renderTransfer();
  renderAwardPrograms();
  renderAwardCost();
}

async function loadPinganRules() {
  try {
    const response = await fetch("/api/pingan-rules", { cache: "no-store" });
    const data = await response.json();
    state.pinganRules = data || { programs: [], assumptions: {} };
    const programs = state.pinganRules.programs?.length || 0;
    $("#pinganRuleStatus").textContent = `已載入 ${programs} 條平安萬里通規則，包含加贈與表格公式成本。`;
  } catch {
    state.pinganRules = { programs: [], assumptions: {} };
    $("#pinganRuleStatus").textContent = "平安萬里通規則載入失敗，仍可用手動比例試算。";
  }
  renderAwardCost();
}

function bindEvents() {
  $$(".owner-tab").forEach(button => {
    button.addEventListener("click", () => {
      state.owner = button.dataset.owner;
      $$(".owner-tab").forEach(tab => tab.classList.toggle("active", tab === button));
      render();
    });
  });

  $$(".view-tab").forEach(button => {
    button.addEventListener("click", () => {
      state.view = button.dataset.view;
      $$(".view-tab").forEach(tab => tab.classList.toggle("active", tab === button));
      $$(".view").forEach(view => view.classList.toggle("active-view", view.id === `${state.view}View`));
    });
  });

  $("#addAccountBtn").addEventListener("click", addAccountInline);
  $("#accountCategory").addEventListener("change", event => populateProgramSelect(event.target.value));
  $("#accountForm").addEventListener("submit", event => {
    if (event.submitter?.value === "cancel") return;
    saveAccount();
  });
  $("#deleteAccountBtn").addEventListener("click", deleteAccount);
  $("#accountList").addEventListener("input", event => {
    const row = event.target.closest(".account-row");
    if (row && event.target.classList.contains("account-input")) updateAccountInline(row);
  });
  $("#accountList").addEventListener("change", event => {
    const row = event.target.closest(".account-row");
    if (row && event.target.classList.contains("account-input")) updateAccountInline(row);
  });
  ["quoteProgram", "quotePoints", "quoteTax", "quoteCurrency", "cashValue"].forEach(id => {
    $(`#${id}`).addEventListener("input", renderQuote);
  });
  ["marriottPoints", "marriottCost", "transferTarget", "transferCashValue", "transferTax", "transferCurrency"].forEach(id => {
    $(`#${id}`).addEventListener("input", renderTransfer);
    $(`#${id}`).addEventListener("change", renderTransfer);
  });
  [
    "awardTripName",
    "awardProgram",
    "awardMiles",
    "awardSeats",
    "awardTax",
    "awardCurrency",
    "awardCashValue",
    "oneWalletPrice",
    "oneWalletPoints",
    "oneWalletFeePct",
    "oneWalletToMileRatio",
    "promoMarriottCost",
    "marriottBonusMode",
  ].forEach(id => {
    $(`#${id}`).addEventListener("input", renderAwardCost);
    $(`#${id}`).addEventListener("change", renderAwardCost);
  });
  $("#saveQuoteBtn").addEventListener("click", saveQuote);
  $("#saveTransferBtn").addEventListener("click", saveTransfer);
  $("#saveAwardCostBtn")?.addEventListener("click", saveAwardCost);
  $("#addPinganRuleBtn").addEventListener("click", addPinganRule);
  $("#savePinganRulesBtn").addEventListener("click", savePinganRules);
  $("#pinganSelectAllBtn").addEventListener("click", () => setPinganDashboardChecks(true));
  $("#pinganSelectNoneBtn").addEventListener("click", () => setPinganDashboardChecks(false));
  $$("[data-save-pingan-preset]").forEach(button => {
    button.addEventListener("click", () => savePinganPreset(button.dataset.savePinganPreset));
  });
  $$("[data-apply-pingan-preset]").forEach(button => {
    button.addEventListener("click", () => applyPinganPreset(button.dataset.applyPinganPreset));
  });
  $$(".pingan-subtab").forEach(button => {
    button.addEventListener("click", () => {
      $$(".pingan-subtab").forEach(tab => tab.classList.toggle("active", tab === button));
      const panel = button.dataset.pinganPanel;
      $("#pinganDashboard").classList.toggle("active-pingan-panel", panel === "dashboard");
      $("#pinganWanlitongPanel").classList.toggle("active-pingan-panel", panel === "wanlitong");
      $("#pinganMarriottPanel").classList.toggle("active-pingan-panel", panel === "marriott");
    });
  });
  $("#pinganRulesBody").addEventListener("click", event => {
    const formulaButton = event.target.closest("[data-toggle-formula]");
    if (formulaButton) {
      const row = $(`[data-formula-index="${formulaButton.dataset.toggleFormula}"]`);
      if (row) {
        row.hidden = !row.hidden;
        formulaButton.textContent = row.hidden ? "公式" : "收合";
      }
      return;
    }
    const button = event.target.closest("[data-delete-pingan]");
    if (!button) return;
    const index = Number(button.dataset.deletePingan);
    state.pinganRules.programs.splice(index, 1);
    renderPinganEditor();
    renderPinganDashboard();
    renderAwardCost();
    schedulePinganSave();
  });
  $("#pinganView").addEventListener("input", event => {
    if (event.target.matches("input, select")) {
      state.pinganRules = collectPinganRules();
      state.data.marriottRules = collectMarriottRules();
      state.data.marriottCostSettings = collectMarriottCostSettings();
      refreshPinganDerivedCosts();
      schedulePinganSave();
    }
  });
  $("#pinganView").addEventListener("change", event => {
    if (event.target.matches("input, select")) {
      state.pinganRules = collectPinganRules();
      state.data.marriottRules = collectMarriottRules();
      state.data.marriottCostSettings = collectMarriottCostSettings();
      refreshPinganDerivedCosts();
      schedulePinganSave();
    }
  });
  $$(".source-filter").forEach(input => {
    input.addEventListener("change", renderAwardCost);
  });
  $("#addOfficialCostBtn").addEventListener("click", addOfficialCost);
  $("#saveOfficialCostsBtn").addEventListener("click", saveOfficialCosts);
  $("#refreshTripplusBtn").addEventListener("click", refreshTripplus);
  $("#officialCostsBody").addEventListener("click", event => {
    const button = event.target.closest("[data-delete-official]");
    if (!button) return;
    const index = Number(button.dataset.deleteOfficial);
    state.officialCosts.programs.splice(index, 1);
    renderOfficialCosts();
    renderAwardCost();
    scheduleOfficialSave();
  });
  $("#officialView").addEventListener("input", event => {
    if (event.target.matches("input, select")) scheduleOfficialSave();
  });
  $("#officialView").addEventListener("change", event => {
    if (event.target.matches("input, select")) scheduleOfficialSave();
  });
  $("#seatSearchBtn").addEventListener("click", searchSeatsAero);
  $("#exportBtn").addEventListener("click", exportJson);
}

bindEvents();
render();
loadRemoteData();
loadRates();
loadTransferRules();
loadPinganRules();
loadOfficialCosts();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}
