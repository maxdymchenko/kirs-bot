(() => {
  const tg = window.Telegram?.WebApp;

  function safeTgCall(fn) {
    if (!tg || typeof fn !== "function") return false;
    try {
      fn();
      return true;
    } catch (_error) {
      // У звичайному браузері (посилання з групи) методи Mini App недоступні
      return false;
    }
  }

  safeTgCall(() => tg.ready());
  safeTgCall(() => tg.expand());

  function safeTgAlert(message) {
    const ok = safeTgCall(() => tg.showAlert(String(message || "")));
    if (!ok && message) {
      // fallback уже є через toast / звичайний UI
      console.info("tg.alert skipped:", message);
    }
    return ok;
  }

  const CART_KEY = "kirs_cart_v1";

  // Fallback, якщо власник ще не зберіг реквізити в «Загальні»
  const PAYMENT_REQUISITES_FALLBACK = {
    recipient: "ФОП (вкажіть отримувача)",
    edrpou: "0000000000",
    iban: "UA000000000000000000000000000",
    bank: "АТ КБ «ПРИВАТБАНК»",
    purpose: "Оплата замовлення",
  };

  let activePaymentRequisites = [];

  const els = {
    bootStatus: document.getElementById("bootStatus"),
    registerView: document.getElementById("registerView"),
    registerForm: document.getElementById("registerForm"),
    registerError: document.getElementById("registerError"),
    ownerView: document.getElementById("ownerView"),
    ownerTabs: document.getElementById("ownerTabs"),
    ownerTabDroppers: document.getElementById("ownerTabDroppers"),
    ownerTabStaff: document.getElementById("ownerTabStaff"),
    ownerTabBalances: document.getElementById("ownerTabBalances"),
    ownerTabReturns: document.getElementById("ownerTabReturns"),
    ownerReturnsList: document.getElementById("ownerReturnsList"),
    ownerReturnsTabs: document.getElementById("ownerReturnsTabs"),
    ownerReturnsDropperFilter: document.getElementById("ownerReturnsDropperFilter"),
    ownerTabSettings: document.getElementById("ownerTabSettings"),
    ownerTabOrder: document.getElementById("ownerTabOrder"),
    ownerTabBlacklist: document.getElementById("ownerTabBlacklist"),
    historyBuckets: document.getElementById("historyBuckets"),
    historyFiltersToggle: document.getElementById("historyFiltersToggle"),
    historyFiltersPanel: document.getElementById("historyFiltersPanel"),
    historyFiltersReset: document.getElementById("historyFiltersReset"),
    historyExcelExport: document.getElementById("historyExcelExport"),
    historyPagePrev: document.getElementById("historyPagePrev"),
    historyPageNext: document.getElementById("historyPageNext"),
    historyPageLabel: document.getElementById("historyPageLabel"),
    historyOrdersCount: document.getElementById("historyOrdersCount"),
    balanceFiltersToggle: document.getElementById("balanceFiltersToggle"),
    balanceFiltersPanel: document.getElementById("balanceFiltersPanel"),
    balanceExcelExport: document.getElementById("balanceExcelExport"),
    balanceFilterStatus: document.getElementById("balanceFilterStatus"),
    balanceFilterDateFrom: document.getElementById("balanceFilterDateFrom"),
    balanceFilterDateTo: document.getElementById("balanceFilterDateTo"),
    ownerBlacklist: document.getElementById("ownerBlacklist"),
    blacklistForm: document.getElementById("blacklistForm"),
    blacklistPhone: document.getElementById("blacklistPhone"),
    blacklistNote: document.getElementById("blacklistNote"),
    blacklistError: document.getElementById("blacklistError"),
    blacklistSearch: document.getElementById("blacklistSearch"),
    blacklistFilterMeta: document.getElementById("blacklistFilterMeta"),
    phoneBlacklistWarn: document.getElementById("phoneBlacklistWarn"),
    ownerDroppers: document.getElementById("ownerDroppers"),
    ownerBroadcastOpen: document.getElementById("ownerBroadcastOpen"),
    ownerBroadcastPanel: document.getElementById("ownerBroadcastPanel"),
    ownerBroadcastText: document.getElementById("ownerBroadcastText"),
    ownerBroadcastSelectAll: document.getElementById("ownerBroadcastSelectAll"),
    ownerBroadcastClearAll: document.getElementById("ownerBroadcastClearAll"),
    ownerBroadcastCount: document.getElementById("ownerBroadcastCount"),
    ownerBroadcastError: document.getElementById("ownerBroadcastError"),
    ownerBroadcastSend: document.getElementById("ownerBroadcastSend"),
    ownerBroadcastCancel: document.getElementById("ownerBroadcastCancel"),
    ownerStaff: document.getElementById("ownerStaff"),
    ownerBalances: document.getElementById("ownerBalances"),
    ownerReferralHistory: document.getElementById("ownerReferralHistory"),
    generalSettingsForm: document.getElementById("generalSettingsForm"),
    generalSettingsError: document.getElementById("generalSettingsError"),
    generalSettingsOk: document.getElementById("generalSettingsOk"),
    npApiKeysList: document.getElementById("npApiKeysList"),
    npApiKeyAdd: document.getElementById("npApiKeyAdd"),
    npWebhookHint: document.getElementById("npWebhookHint"),
    paymentRequisitesList: document.getElementById("paymentRequisitesList"),
    paymentRequisiteAdd: document.getElementById("paymentRequisiteAdd"),
    senderCity: document.getElementById("senderCity"),
    senderCityDropdown: document.getElementById("senderCityDropdown"),
    senderCityRef: document.getElementById("senderCityRef"),
    senderSettlementRef: document.getElementById("senderSettlementRef"),
    senderWarehouse: document.getElementById("senderWarehouse"),
    senderWarehouseDropdown: document.getElementById("senderWarehouseDropdown"),
    senderWarehouseRef: document.getElementById("senderWarehouseRef"),
    senderWarehouseNumber: document.getElementById("senderWarehouseNumber"),
    parcelWeight: document.getElementById("parcelWeight"),
    parcelLength: document.getElementById("parcelLength"),
    parcelWidth: document.getElementById("parcelWidth"),
    parcelHeight: document.getElementById("parcelHeight"),
    parcelSeats: document.getElementById("parcelSeats"),
    parcelDescription: document.getElementById("parcelDescription"),
    ordersSheetUrl: document.getElementById("ordersSheetUrl"),
    ordersSheetColumnsHint: document.getElementById("ordersSheetColumnsHint"),
    balanceView: document.getElementById("balanceView"),
    balanceHero: document.getElementById("balanceHero"),
    balanceConditional: document.getElementById("balanceConditional"),
    balanceReferralTotal: document.getElementById("balanceReferralTotal"),
    balanceStats: document.getElementById("balanceStats"),
    balanceLedger: document.getElementById("balanceLedger"),
    balanceHint: document.getElementById("balanceHint"),
    dropperSettingsView: document.getElementById("dropperSettingsView"),
    notifyShippingEvents: document.getElementById("notifyShippingEvents"),
    dropperSettingsStatus: document.getElementById("dropperSettingsStatus"),
    staffForm: document.getElementById("staffForm"),
    staffError: document.getElementById("staffError"),
    warehouseView: document.getElementById("warehouseView"),
    warehouseTabs: document.getElementById("warehouseTabs"),
    warehouseTabCatalog: document.getElementById("warehouseTabCatalog"),
    warehouseTabPacking: document.getElementById("warehouseTabPacking"),
    warehouseTabShipping: document.getElementById("warehouseTabShipping"),
    warehouseTabSalary: document.getElementById("warehouseTabSalary"),
    warehouseSearchForm: document.getElementById("warehouseSearchForm"),
    warehouseSearchInput: document.getElementById("warehouseSearchInput"),
    warehouseSearchStatus: document.getElementById("warehouseSearchStatus"),
    warehouseResults: document.getElementById("warehouseResults"),
    warehousePackingList: document.getElementById("warehousePackingList"),
    warehouseShippingList: document.getElementById("warehouseShippingList"),
    warehousePrintBtn: document.getElementById("warehousePrintBtn"),
    warehouseSelectAllBtn: document.getElementById("warehouseSelectAllBtn"),
    warehouseDeselectAllBtn: document.getElementById("warehouseDeselectAllBtn"),
    orderMain: document.getElementById("orderMain"),
    searchForm: document.getElementById("searchForm"),
    searchInput: document.getElementById("searchInput"),
    colorFilter: document.getElementById("colorFilter"),
    colorDropdown: document.getElementById("colorDropdown"),
    filtersToggle: document.getElementById("filtersToggle"),
    filtersPanel: document.getElementById("filtersPanel"),
    filtersBadge: document.getElementById("filtersBadge"),
    filtersClear: document.getElementById("filtersClear"),
    status: document.getElementById("status"),
    results: document.getElementById("results"),
    catalogView: document.getElementById("catalogView"),
    cartView: document.getElementById("cartView"),
    checkoutView: document.getElementById("checkoutView"),
    confirmView: document.getElementById("confirmView"),
    confirmSummary: document.getElementById("confirmSummary"),
    confirmError: document.getElementById("confirmError"),
    confirmBack: document.getElementById("confirmBack"),
    confirmSubmit: document.getElementById("confirmSubmit"),
    historyView: document.getElementById("historyView"),
    ordersHistory: document.getElementById("ordersHistory"),
    mainTabs: document.getElementById("mainTabs"),
    cartList: document.getElementById("cartList"),
    cartEmpty: document.getElementById("cartEmpty"),
    cartFooter: document.getElementById("cartFooter"),
    cartCount: document.getElementById("cartCount"),
    cartSum: document.getElementById("cartSum"),
    cartBadge: document.getElementById("cartBadge"),
    cartChipText: document.getElementById("cartChipText"),
    cartChip: document.getElementById("cartChip"),
    topbarActions: document.getElementById("topbarActions"),
    settingsChip: document.getElementById("settingsChip"),
    photoZoomBackdrop: document.getElementById("photoZoomBackdrop"),
    checkoutBtn: document.getElementById("checkoutBtn"),
    checkoutBack: document.getElementById("checkoutBack"),
    checkoutForm: document.getElementById("checkoutForm"),
    checkoutError: document.getElementById("checkoutError"),
    firstName: document.getElementById("firstName"),
    patronymic: document.getElementById("patronymic"),
    patronymicHint: document.getElementById("patronymicHint"),
    lastName: document.getElementById("lastName"),
    ownTtn: document.getElementById("ownTtn"),
    ownTtnToggleRow: document.getElementById("ownTtnToggleRow"),
    paymentEstimatedSlot: document.getElementById("paymentEstimatedSlot"),
    estimatedCostBlock: document.getElementById("estimatedCostBlock"),
    estimatedCost: document.getElementById("estimatedCost"),
    estimatedCostLabel: document.getElementById("estimatedCostLabel"),
    estimatedCostHint: document.getElementById("estimatedCostHint"),
    prepayField: document.getElementById("prepayField"),
    codAmountField: document.getElementById("codAmountField"),
    ttnFields: document.getElementById("ttnFields"),
    ttnNpBlock: document.getElementById("ttnNpBlock"),
    ttnRmpBlock: document.getElementById("ttnRmpBlock"),
    ttnNumber: document.getElementById("ttnNumber"),
    rmpNumber: document.getElementById("rmpNumber"),
    recipientNameFields: document.getElementById("recipientNameFields"),
    deliverySection: document.getElementById("deliverySection"),
    phoneFieldLabel: document.getElementById("phoneFieldLabel"),
    balancePaymentCard: document.getElementById("balancePaymentCard"),
    balancePayHint: document.getElementById("balancePayHint"),
    warehouseField: document.getElementById("warehouseField"),
    courierAddressFields: document.getElementById("courierAddressFields"),
    warehouseLabel: document.getElementById("warehouseLabel"),
    street: document.getElementById("street"),
    streetRef: document.getElementById("streetRef"),
    streetDropdown: document.getElementById("streetDropdown"),
    house: document.getElementById("house"),
    apartment: document.getElementById("apartment"),
    codPaymentHint: document.getElementById("codPaymentHint"),
    codPaymentCard: document.getElementById("codPaymentCard"),
    requisitesPaymentCard: document.getElementById("requisitesPaymentCard"),
    prepayBlock: document.getElementById("prepayBlock"),
    prepayHint: document.getElementById("prepayHint"),
    prepay: document.getElementById("prepay"),
    codAmount: document.getElementById("codAmount"),
    requisitesBlock: document.getElementById("requisitesBlock"),
    requisitesDetails: document.getElementById("requisitesDetails"),
    payAmountLabel: document.getElementById("payAmountLabel"),
    requisitesIntro: document.getElementById("requisitesIntro"),
    ttnPdfField: document.getElementById("ttnPdfField"),
    ttnPdf: document.getElementById("ttnPdf"),
    ttnPdfName: document.getElementById("ttnPdfName"),
    phone: document.getElementById("phone"),
    phoneGhost: document.getElementById("phoneGhost"),
    city: document.getElementById("city"),
    cityRef: document.getElementById("cityRef"),
    settlementRef: document.getElementById("settlementRef"),
    cityDropdown: document.getElementById("cityDropdown"),
    warehouse: document.getElementById("warehouse"),
    warehouseRef: document.getElementById("warehouseRef"),
    warehouseDropdown: document.getElementById("warehouseDropdown"),
    rolePreviewBar: document.getElementById("rolePreviewBar"),
    previewRoleSelect: document.getElementById("previewRoleSelect"),
    previewDropperWrap: document.getElementById("previewDropperWrap"),
    previewDropperSelect: document.getElementById("previewDropperSelect"),
    previewBackOwner: document.getElementById("previewBackOwner"),
    previewBanner: document.getElementById("previewBanner"),
  };

  const dropperSettings = {
    chat_id: "",
    allow_cod: true,
    allow_balance_payment: false,
    allow_negative_balance: false,
    negative_balance_limit: 0,
    balance: 0,
    extra_discount_percent: 0,
    orders_disabled: false,
    referral_code: "",
    referral_percent: 0,
    notify_shipping_events: false,
  };

  const sessionState = {
    role: "guest",
    chat_id: "",
    user_id: "",
    username: "",
    need_registration: false,
    block_reason: "",
  };

  let warehouseTabState = "catalog";

  const previewState = {
    mode: "owner",
    dropperChatId: "",
    droppersLoaded: false,
    cartForChatId: "",
  };

  const PHONE_EXAMPLE = "+380(99)999-99-99";
  const PHONE_PREFIX_DIGITS = "380";
  const PHONE_MAX_DIGITS = 12;
  const PHONE_PREFIX_DISPLAY = "+380(";

  const blacklistState = {
    items: [],
    search: "",
  };

  const ownerReturnsState = {
    bucket: "awaiting_receipt",
    counts: {},
  };

  const npState = {
    city: null,
    warehouse: null,
    warehouseCache: { cityRef: "", query: "", items: [] },
    street: null,
    cityTimer: null,
    warehouseTimer: null,
    streetTimer: null,
    cityReq: 0,
    warehouseReq: 0,
    streetReq: 0,
  };

  function loadCart() {
    try {
      return JSON.parse(localStorage.getItem(CART_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function saveCart(cart) {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
    updateCartIndicators();
  }

  function cartKey(item) {
    return `${item.product_id || ""}|${item.code}|${item.color || ""}`;
  }

  function parsePrice(value) {
    const n = Number(String(value ?? "").replace(",", ".").replace(/[^\d.]/g, ""));
    return Number.isFinite(n) ? n : 0;
  }

  function roundMoney(amount) {
    return Math.round((Number(amount) || 0) * 100) / 100;
  }

  function formatMoneyAmount(amount) {
    const n = roundMoney(amount);
    if (Math.abs(n - Math.round(n)) < 1e-9) return String(Math.round(n));
    return n.toFixed(2).replace(/\.?0+$/, "");
  }

  function formatMoney(amount) {
    return `${formatMoneyAmount(amount)} ₴`;
  }

  function hasDiscountPrice(item) {
    if (!item) return false;
    const original = item.drop_price_original;
    if (original == null || original === "") return false;
    return String(original) !== String(item.drop_price || "");
  }

  function renderPriceHtml(item, { withCurrency = true } = {}) {
    const cur = withCurrency ? " ₴" : "";
    const discounted = item?.drop_price != null && item.drop_price !== "" ? String(item.drop_price) : "";
    if (!discounted) return `<div class="price">—</div>`;
    if (hasDiscountPrice(item)) {
      return `<div class="price-block">
        <div class="price-old">${escapeHtml(String(item.drop_price_original))}${cur}</div>
        <div class="price price-new">${escapeHtml(discounted)}${cur}</div>
      </div>`;
    }
    return `<div class="price">${escapeHtml(discounted)}${cur}</div>`;
  }

  function cartQtyTotal(cart = loadCart()) {
    return cart.reduce((sum, item) => sum + (item.qty || 1), 0);
  }

  function cartMoneyTotal(cart = loadCart()) {
    const sum = cart.reduce(
      (acc, item) => acc + parsePrice(item.drop_price) * (item.qty || 1),
      0
    );
    return roundMoney(sum);
  }

  function updateCartIndicators() {
    const cart = loadCart();
    const qty = cartQtyTotal(cart);
    const sum = cartMoneyTotal(cart);
    els.cartBadge.textContent = String(qty);
    els.cartChipText.textContent = qty ? `${qty} | ${formatMoney(sum)}` : "0";
  }

  let phoneDigits = PHONE_PREFIX_DIGITS;

  function normalizePhoneDigits(raw) {
    let digits = String(raw || "").replace(/\D/g, "");
    if (!digits) return PHONE_PREFIX_DIGITS;

    if (digits.startsWith("380")) {
      digits = digits.slice(0, PHONE_MAX_DIGITS);
    } else if (digits.startsWith("38")) {
      digits = digits.slice(0, PHONE_MAX_DIGITS);
      if (digits.length < 3) digits = PHONE_PREFIX_DIGITS;
    } else if (digits.startsWith("0")) {
      digits = ("38" + digits).slice(0, PHONE_MAX_DIGITS);
    } else {
      digits = (PHONE_PREFIX_DIGITS + digits).slice(0, PHONE_MAX_DIGITS);
    }

    if (!digits.startsWith("380") || digits.length < 3) {
      return PHONE_PREFIX_DIGITS;
    }
    return digits;
  }

  function formatPhonePartial(digits) {
    const d = digits && digits.length >= 3 ? digits : PHONE_PREFIX_DIGITS;
    // +380(XX)XXX-XX-XX
    let result = "+380(";
    if (d.length <= 3) return result;

    result += d.slice(3, Math.min(5, d.length));
    if (d.length >= 5) {
      result += ")";
      if (d.length > 5) {
        result += d.slice(5, Math.min(8, d.length));
        if (d.length >= 8) {
          result += "-" + d.slice(8, Math.min(10, d.length));
          if (d.length >= 10) {
            result += "-" + d.slice(10, Math.min(12, d.length));
          }
        }
      }
    }
    return result;
  }

  function updatePhoneGhost(formatted) {
    if (!els.phoneGhost) return;
    if (!formatted || formatted.length >= PHONE_EXAMPLE.length) {
      els.phoneGhost.textContent = "";
      return;
    }
    els.phoneGhost.textContent =
      "\u00A0".repeat(formatted.length) + PHONE_EXAMPLE.slice(formatted.length);
  }

  function setPhoneDigits(rawDigits) {
    phoneDigits = normalizePhoneDigits(rawDigits);
    const formatted = formatPhonePartial(phoneDigits);
    els.phone.value = formatted;
    updatePhoneGhost(formatted);
    try {
      const pos = formatted.length;
      els.phone.setSelectionRange(pos, pos);
    } catch {
      /* ignore */
    }
    void checkPhoneBlacklist();
    return formatted;
  }

  function resetPhoneField() {
    setPhoneDigits(PHONE_PREFIX_DIGITS);
  }

  function isPhoneComplete() {
    return phoneDigits.length === PHONE_MAX_DIGITS;
  }

  let phoneBlacklisted = false;
  let phoneBlacklistTimer = null;

  function setPhoneBlacklistWarn(message) {
    phoneBlacklisted = Boolean(message);
    if (!els.phoneBlacklistWarn) return;
    if (message) {
      els.phoneBlacklistWarn.textContent = message;
      els.phoneBlacklistWarn.classList.remove("hidden");
    } else {
      els.phoneBlacklistWarn.textContent = "";
      els.phoneBlacklistWarn.classList.add("hidden");
    }
  }

  async function checkPhoneBlacklist() {
    if (phoneBlacklistTimer) {
      clearTimeout(phoneBlacklistTimer);
      phoneBlacklistTimer = null;
    }
    if (!isPhoneComplete()) {
      setPhoneBlacklistWarn("");
      return;
    }
    phoneBlacklistTimer = setTimeout(async () => {
      try {
        const response = await fetch(
          `/api/checkout/blacklist-check?phone=${encodeURIComponent(phoneDigits)}`
        );
        const data = await response.json();
        if (!response.ok) {
          setPhoneBlacklistWarn("");
          return;
        }
        setPhoneBlacklistWarn(data.blocked ? data.message || "Клієнт у чорному списку" : "");
      } catch {
        setPhoneBlacklistWarn("");
      }
    }, 280);
  }

  function showToast(text, durationMs = 2200) {
    const node = document.createElement("div");
    node.className = "toast";
    node.textContent = text;
    document.body.appendChild(node);
    const ms = Math.max(800, Number(durationMs) || 2200);
    setTimeout(() => node.remove(), ms);
  }

  function setCheckoutError(message) {
    if (!message) {
      els.checkoutError.classList.add("hidden");
      els.checkoutError.textContent = "";
      return;
    }
    els.checkoutError.textContent = message;
    els.checkoutError.classList.remove("hidden");
  }

  let checkoutDraft = null;

  function switchTab(name) {
    closePhotoZoom();
    if (els.mainTabs) {
      els.mainTabs.querySelectorAll("[data-tab]").forEach((tab) => {
        tab.classList.toggle("active", tab.dataset.tab === name);
      });
    }
    els.mainTabs.classList.remove("hidden");
    els.catalogView.classList.toggle("hidden", name !== "catalog");
    els.cartView.classList.toggle("hidden", name !== "cart");
    if (els.historyView) els.historyView.classList.toggle("hidden", name !== "history");
    if (els.balanceView) els.balanceView.classList.toggle("hidden", name !== "balance");
    if (els.dropperSettingsView) {
      els.dropperSettingsView.classList.toggle("hidden", name !== "settings");
    }
    els.checkoutView.classList.add("hidden");
    if (els.confirmView) els.confirmView.classList.add("hidden");
    if (name === "cart") renderCart();
    if (name === "history") renderOrdersHistory();
    if (name === "balance") renderBalanceView();
    if (name === "settings") renderDropperSettingsView();
  }

  async function openCheckout() {
    const cart = loadCart();
    if (!cart.length) return;
    els.catalogView.classList.add("hidden");
    els.cartView.classList.add("hidden");
    if (els.historyView) els.historyView.classList.add("hidden");
    if (els.balanceView) els.balanceView.classList.add("hidden");
    if (els.dropperSettingsView) els.dropperSettingsView.classList.add("hidden");
    if (els.confirmView) els.confirmView.classList.add("hidden");
    els.checkoutView.classList.remove("hidden");
    els.mainTabs.classList.add("hidden");
    if (els.mainTabs) {
      els.mainTabs.querySelectorAll("[data-tab]").forEach((tab) => tab.classList.remove("active"));
    }
    await loadDropperSettings();
    renderRequisitesDetails();
    syncDeliveryFields();
    syncPaymentAndTtn();
    resetPhoneField();
    setCheckoutError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function syncDeliveryFields() {
    const method =
      els.checkoutForm.querySelector('input[name="deliveryMethod"]:checked')?.value ||
      "np_warehouse";
    const isCourier = method === "np_courier";
    els.warehouseField.classList.toggle("hidden", isCourier);
    els.courierAddressFields.classList.toggle("hidden", !isCourier);
    if (!isCourier) {
      els.warehouseLabel.textContent = "Відділення/поштомат Нової Пошти";
    }
    if (els.patronymicHint) {
      els.patronymicHint.textContent = isCourier
        ? "Обовʼязково для доставки курʼєром"
        : "Необовʼязково (для курʼєра — обовʼязково)";
    }
    syncWarehouseEnabled();
    syncStreetEnabled();
  }

  function syncWarehouseEnabled() {
    const hasCity = Boolean(npState.city?.city_ref);
    els.warehouse.disabled = !hasCity;
    if (!hasCity) {
      clearWarehouseSelection({ keepText: false });
    }
  }

  function syncStreetEnabled() {
    const hasCity = Boolean(npState.city?.settlement_ref || npState.city?.city_ref);
    els.street.disabled = !hasCity;
    if (!hasCity) {
      clearStreetSelection({ keepText: false });
    }
  }

  function markSelected(fieldEl, selected) {
    fieldEl?.closest(".ac-field")?.classList.toggle("is-selected", Boolean(selected));
  }

  function hideDropdown(dropdown) {
    dropdown.classList.add("hidden");
    dropdown.innerHTML = "";
  }

  function showDropdownMessage(dropdown, text, className = "ac-empty") {
    dropdown.innerHTML = `<div class="${className}">${escapeHtml(text)}</div>`;
    dropdown.classList.remove("hidden");
  }

  function clearCitySelection({ keepText = true } = {}) {
    npState.city = null;
    els.cityRef.value = "";
    els.settlementRef.value = "";
    if (!keepText) els.city.value = "";
    markSelected(els.city, false);
    clearWarehouseSelection({ keepText: false });
    clearStreetSelection({ keepText: false });
    syncWarehouseEnabled();
    syncStreetEnabled();
  }

  function clearWarehouseSelection({ keepText = true } = {}) {
    npState.warehouse = null;
    npState.warehouseCache = { cityRef: "", query: "", items: [] };
    els.warehouseRef.value = "";
    if (!keepText) els.warehouse.value = "";
    markSelected(els.warehouse, false);
    hideDropdown(els.warehouseDropdown);
  }

  function clearStreetSelection({ keepText = true } = {}) {
    npState.street = null;
    els.streetRef.value = "";
    if (!keepText) els.street.value = "";
    markSelected(els.street, false);
    hideDropdown(els.streetDropdown);
  }

  function selectCity(item) {
    npState.city = item;
    els.city.value = item.label || item.present || item.main_description || "";
    els.cityRef.value = item.city_ref || "";
    els.settlementRef.value = item.settlement_ref || "";
    markSelected(els.city, true);
    hideDropdown(els.cityDropdown);
    clearWarehouseSelection({ keepText: false });
    clearStreetSelection({ keepText: false });
    syncWarehouseEnabled();
    syncStreetEnabled();

    const method =
      els.checkoutForm.querySelector('input[name="deliveryMethod"]:checked')?.value ||
      "np_warehouse";
    if (method === "np_courier") {
      els.street.focus();
    } else {
      els.warehouse.focus();
    }
  }

  function selectWarehouse(item) {
    npState.warehouse = item;
    els.warehouse.value = item.label || item.description || "";
    els.warehouseRef.value = item.ref || "";
    markSelected(els.warehouse, true);
    hideDropdown(els.warehouseDropdown);
  }

  function selectStreet(item) {
    npState.street = item;
    els.street.value = item.label || item.present || item.description || "";
    els.streetRef.value = item.ref || "";
    markSelected(els.street, true);
    hideDropdown(els.streetDropdown);
    els.house.focus();
  }

  function renderCityOptions(items) {
    if (!items.length) {
      showDropdownMessage(els.cityDropdown, "Нічого не знайдено. Спробуйте іншу назву.");
      return;
    }
    els.cityDropdown.innerHTML = items
      .map((item, index) => {
        const title = item.label || item.present || item.main_description || "";
        const parts = [item.area, item.region].filter(Boolean).join(", ");
        return `
          <button type="button" class="ac-option" role="option" data-city-index="${index}">
            <span>${escapeHtml(title)}</span>
            ${parts ? `<span class="ac-option-sub">${escapeHtml(parts)}</span>` : ""}
          </button>
        `;
      })
      .join("");
    els.cityDropdown.dataset.items = JSON.stringify(items);
    els.cityDropdown.classList.remove("hidden");
  }

  function renderWarehouseOptions(items) {
    if (!items.length) {
      showDropdownMessage(
        els.warehouseDropdown,
        "Нічого не знайдено. Введіть номер або частину адреси."
      );
      return;
    }
    els.warehouseDropdown.innerHTML = items
      .map((item, index) => {
        const title = item.label || item.description || "";
        const sub = item.number ? `№ ${item.number}` : "";
        return `
          <button type="button" class="ac-option" role="option" data-wh-index="${index}">
            <span>${escapeHtml(title)}</span>
            ${sub ? `<span class="ac-option-sub">${escapeHtml(sub)}</span>` : ""}
          </button>
        `;
      })
      .join("");
    els.warehouseDropdown.dataset.items = JSON.stringify(items);
    els.warehouseDropdown.classList.remove("hidden");
  }

  async function searchCities(query) {
    const reqId = ++npState.cityReq;
    showDropdownMessage(els.cityDropdown, "Шукаємо...", "ac-loading");
    try {
      const response = await fetch(
        `/api/np/settlements?q=${encodeURIComponent(query)}&limit=20`
      );
      const data = await response.json();
      if (reqId !== npState.cityReq) return;
      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string" ? data.detail : "Помилка пошуку міст"
        );
      }
      renderCityOptions(data.items || []);
    } catch (error) {
      if (reqId !== npState.cityReq) return;
      showDropdownMessage(
        els.cityDropdown,
        error.message || "Не вдалося завантажити міста"
      );
    }
  }

  function normalizeWarehouseQuery(value) {
    return String(value || "")
      .trim()
      .replace(/^(?:№|#|no\.?)\s*/i, "")
      .replace(/^(?:відділення|отделение|поштомат|почтомат)\s*/i, "")
      .trim();
  }

  async function searchWarehouses(query) {
    const cityRef = npState.city?.city_ref || els.cityRef.value;
    if (!cityRef) return;
    const q = normalizeWarehouseQuery(query);
    const limit = q ? 10 : 20;

    if (
      npState.warehouseCache.cityRef === cityRef &&
      npState.warehouseCache.query === q &&
      Array.isArray(npState.warehouseCache.items) &&
      npState.warehouseCache.items.length
    ) {
      renderWarehouseOptions(npState.warehouseCache.items);
      return;
    }

    const reqId = ++npState.warehouseReq;
    showDropdownMessage(els.warehouseDropdown, "Шукаємо...", "ac-loading");
    try {
      const response = await fetch(
        `/api/np/warehouses?city_ref=${encodeURIComponent(cityRef)}&q=${encodeURIComponent(q)}&limit=${limit}`
      );
      const data = await response.json();
      if (reqId !== npState.warehouseReq) return;
      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string" ? data.detail : "Помилка пошуку відділень"
        );
      }
      const items = data.items || [];
      npState.warehouseCache = { cityRef, query: q, items };
      renderWarehouseOptions(items);
    } catch (error) {
      if (reqId !== npState.warehouseReq) return;
      showDropdownMessage(
        els.warehouseDropdown,
        error.message || "Не вдалося завантажити відділення"
      );
    }
  }

  function scheduleCitySearch(value) {
    clearTimeout(npState.cityTimer);
    const query = value.trim();
    if (query.length < 2) {
      hideDropdown(els.cityDropdown);
      return;
    }
    npState.cityTimer = setTimeout(() => searchCities(query), 300);
  }

  function scheduleWarehouseSearch(value) {
    clearTimeout(npState.warehouseTimer);
    const query = value.trim();
    if (!npState.city?.city_ref && !els.cityRef.value) return;
    // Порожній запит = показати перші відділення; з номером — коротший debounce
    const delay = query ? 220 : 0;
    npState.warehouseTimer = setTimeout(() => searchWarehouses(query), delay);
  }

  function renderStreetOptions(items) {
    if (!items.length) {
      showDropdownMessage(els.streetDropdown, "Нічого не знайдено. Спробуйте іншу назву.");
      return;
    }
    els.streetDropdown.innerHTML = items
      .map((item, index) => {
        const title = item.label || item.present || item.description || "";
        return `
          <button type="button" class="ac-option" role="option" data-street-index="${index}">
            <span>${escapeHtml(title)}</span>
          </button>
        `;
      })
      .join("");
    els.streetDropdown.dataset.items = JSON.stringify(items);
    els.streetDropdown.classList.remove("hidden");
  }

  async function searchStreets(query) {
    const settlementRef = npState.city?.settlement_ref || els.settlementRef.value;
    const cityRef = npState.city?.city_ref || els.cityRef.value;
    if (!settlementRef && !cityRef) return;
    const reqId = ++npState.streetReq;
    showDropdownMessage(els.streetDropdown, "Шукаємо...", "ac-loading");
    try {
      const params = new URLSearchParams({
        q: query,
        limit: "20",
      });
      if (settlementRef) params.set("settlement_ref", settlementRef);
      if (cityRef) params.set("city_ref", cityRef);
      const response = await fetch(`/api/np/streets?${params.toString()}`);
      const data = await response.json();
      if (reqId !== npState.streetReq) return;
      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string" ? data.detail : "Помилка пошуку вулиць"
        );
      }
      renderStreetOptions(data.items || []);
    } catch (error) {
      if (reqId !== npState.streetReq) return;
      showDropdownMessage(
        els.streetDropdown,
        error.message || "Не вдалося завантажити вулиці"
      );
    }
  }

  function scheduleStreetSearch(value) {
    clearTimeout(npState.streetTimer);
    const query = value.trim();
    if (!(npState.city?.settlement_ref || npState.city?.city_ref)) return;
    if (query.length < 2) {
      hideDropdown(els.streetDropdown);
      return;
    }
    npState.streetTimer = setTimeout(() => searchStreets(query), 300);
  }

  function renderRequisitesDetails() {
    if (!els.requisitesDetails) return;
    const items =
      Array.isArray(activePaymentRequisites) && activePaymentRequisites.length
        ? activePaymentRequisites
        : [
            {
              kind: "fop",
              label: "",
              ...PAYMENT_REQUISITES_FALLBACK,
            },
          ];
    els.requisitesDetails.innerHTML = items
      .map((row) => {
        const kind = row.kind === "card" ? "card" : "fop";
        const title =
          (row.label || "").trim() ||
          (kind === "card" ? "Картка" : "ФОП / рахунок");
        const lines = [];
        if (row.recipient) {
          lines.push(
            `<div><strong>Отримувач:</strong> ${escapeHtml(row.recipient)}</div>`
          );
        }
        if (kind === "fop") {
          if (row.edrpou) {
            lines.push(
              `<div><strong>ЄДРПОУ:</strong> ${escapeHtml(row.edrpou)}</div>`
            );
          }
          if (row.iban) {
            lines.push(
              `<div><strong>Рахунок IBAN:</strong> ${escapeHtml(row.iban)}</div>`
            );
          }
        } else if (row.card_number) {
          lines.push(
            `<div><strong>Картка:</strong> ${escapeHtml(row.card_number)}</div>`
          );
        }
        if (row.bank) {
          lines.push(`<div><strong>Банк:</strong> ${escapeHtml(row.bank)}</div>`);
        }
        if (row.purpose) {
          lines.push(
            `<div><strong>Призначення:</strong> ${escapeHtml(row.purpose)}</div>`
          );
        }
        if (!lines.length) {
          lines.push(`<div>${escapeHtml("Реквізити не заповнені")}</div>`);
        }
        return `<div class="requisites-account">
          <div class="requisites-account-title">${escapeHtml(title)}</div>
          ${lines.join("")}
        </div>`;
      })
      .join("");
  }

  function selectedPaymentMethod() {
    const checked = els.checkoutForm.querySelector(
      'input[name="paymentMethod"]:checked:not([disabled])'
    );
    if (checked) return checked.value;
    if (isFlagEnabled(dropperSettings.allow_cod, true) && !els.ownTtn?.checked) {
      return "cod";
    }
    return "requisites";
  }

  function queryParam(name) {
    try {
      return new URLSearchParams(window.location.search).get(name) || "";
    } catch (_error) {
      return "";
    }
  }

  function currentTelegramChatId() {
    if (sessionState.chat_id) return sessionState.chat_id;
    const unsafe = tg?.initDataUnsafe || {};
    if (unsafe.chat?.id != null) return String(unsafe.chat.id);
    const fromQuery = queryParam("chat_id");
    if (fromQuery) return fromQuery;
    return "";
  }

  function isOwnerRolePreview() {
    return sessionState.role === "owner" && previewState.mode !== "owner";
  }

  function effectiveDropperChatId() {
    if (
      sessionState.role === "owner" &&
      previewState.mode === "dropper" &&
      previewState.dropperChatId
    ) {
      return previewState.dropperChatId;
    }
    return currentTelegramChatId();
  }

  function currentTelegramUser() {
    const unsafe = tg?.initDataUnsafe || {};
    return {
      user_id:
        sessionState.user_id ||
        (unsafe.user?.id != null ? String(unsafe.user.id) : "") ||
        queryParam("user_id"),
      username: sessionState.username || unsafe.user?.username || "",
    };
  }

  function isFlagEnabled(value, defaultOn = true) {
    if (value === undefined || value === null || value === "") return defaultOn;
    if (value === false || value === 0 || value === "0" || value === "false") return false;
    return Boolean(value);
  }

  async function loadDropperSettings(chatIdOverride) {
    const chatId =
      chatIdOverride != null && String(chatIdOverride).trim()
        ? String(chatIdOverride).trim()
        : effectiveDropperChatId();
    dropperSettings.chat_id = chatId;
    try {
      const response = await fetch(
        `/api/dropper/settings?chat_id=${encodeURIComponent(chatId)}`
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "settings error");
      }
      // Явно false/0 з API = вимкнено; відсутнє поле → увімкнено (сумісність)
      dropperSettings.allow_cod = isFlagEnabled(data.allow_cod, false);
      dropperSettings.allow_balance_payment = Boolean(data.allow_negative_balance);
      dropperSettings.allow_negative_balance = Boolean(data.allow_negative_balance);
      dropperSettings.negative_balance_limit = Number(data.negative_balance_limit || 0);
      dropperSettings.balance = Number(data.balance || 0);
      dropperSettings.extra_discount_percent = Number(data.extra_discount_percent || 0);
      dropperSettings.orders_disabled = Boolean(data.orders_disabled);
      dropperSettings.referral_code = data.referral_code || "";
      dropperSettings.referral_percent = Number(data.referral_percent || 0);
      dropperSettings.notify_shipping_events = Boolean(data.notify_shipping_events);
      if (data.chat_id) dropperSettings.chat_id = String(data.chat_id);
      activePaymentRequisites = Array.isArray(data.payment_requisites)
        ? data.payment_requisites
        : [];
      renderRequisitesDetails();
    } catch (error) {
      console.warn("dropper settings", error);
      // При помилці налаштувань не показуємо наложку «на всяк випадок»
      dropperSettings.allow_cod = false;
      dropperSettings.allow_balance_payment = false;
      dropperSettings.allow_negative_balance = false;
      dropperSettings.negative_balance_limit = 0;
      dropperSettings.balance = 0;
      dropperSettings.extra_discount_percent = 0;
      dropperSettings.orders_disabled = false;
      dropperSettings.notify_shipping_events = false;
      try {
        const reqRes = await fetch("/api/payment-requisites");
        const reqData = await reqRes.json();
        if (reqRes.ok && Array.isArray(reqData.items)) {
          activePaymentRequisites = reqData.items;
        }
      } catch (_e) {
        /* keep previous */
      }
      renderRequisitesDetails();
    }
  }

  async function loadColorOptions() {
    // colors now load via autocomplete; keep as no-op for callers
  }

  const colorState = {
    timer: null,
    req: 0,
    selected: "",
  };

  function syncFiltersUi() {
    const active = Boolean(colorState.selected || (els.colorFilter?.value || "").trim());
    if (els.filtersBadge) {
      els.filtersBadge.classList.toggle("hidden", !active);
      els.filtersBadge.textContent = active ? "1" : "";
    }
    if (els.filtersClear) {
      els.filtersClear.classList.toggle("hidden", !active);
    }
    if (els.filtersToggle) {
      els.filtersToggle.classList.toggle("is-active", active);
    }
  }

  function setColorFilter(value, { runSearch = false } = {}) {
    colorState.selected = (value || "").trim();
    if (els.colorFilter) els.colorFilter.value = colorState.selected;
    hideDropdown(els.colorDropdown);
    syncFiltersUi();
    if (runSearch && els.searchForm && (els.searchInput.value.trim() || colorState.selected)) {
      els.searchForm.requestSubmit();
    }
  }

  function renderColorOptions(items) {
    if (!els.colorDropdown) return;
    if (!items.length) {
      showDropdownMessage(els.colorDropdown, "Нічого не знайдено");
      return;
    }
    els.colorDropdown.innerHTML = items
      .map(
        (color, index) => `
      <button type="button" class="ac-option" data-color-index="${index}" role="option">
        ${escapeHtml(color)}
      </button>`
      )
      .join("");
    els.colorDropdown.dataset.items = JSON.stringify(items);
    els.colorDropdown.classList.remove("hidden");
  }

  async function searchColors(query) {
    if (!els.colorDropdown) return;
    const reqId = ++colorState.req;
    showDropdownMessage(els.colorDropdown, "Шукаємо...", "ac-loading");
    try {
      const response = await fetch(
        `/api/products/colors?q=${encodeURIComponent(query)}&limit=40`
      );
      const data = await response.json();
      if (reqId !== colorState.req) return;
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Помилка кольорів");
      }
      renderColorOptions(data.items || []);
    } catch (error) {
      if (reqId !== colorState.req) return;
      showDropdownMessage(els.colorDropdown, error.message || "Не вдалося завантажити");
    }
  }

  function scheduleColorSearch(value) {
    clearTimeout(colorState.timer);
    const query = value.trim();
    colorState.timer = setTimeout(() => searchColors(query), query ? 220 : 0);
  }

  function updateRequisitesIntro(total) {
    if (!els.requisitesIntro) return;
    const amount = `${formatMoneyAmount(total)} грн`;
    els.requisitesIntro.innerHTML =
      `Виконайте оплату в розмірі <strong id="payAmountLabel">${amount}</strong> за реквізитами.`;
    els.payAmountLabel = document.getElementById("payAmountLabel");
  }

  function balanceSpendRoom() {
    if (!dropperSettings.allow_negative_balance) return 0;
    const balance = Number(dropperSettings.balance || 0);
    const floor = dropperSettings.allow_negative_balance
      ? -Math.max(0, Number(dropperSettings.negative_balance_limit || 0))
      : 0;
    return Math.max(0, Math.floor(balance - floor));
  }

  function maxPrepayAmount(orderTotal) {
    const total = Math.max(0, roundMoney(orderTotal));
    return roundMoney(total + balanceSpendRoom());
  }

  function updatePrepayUi(orderTotal) {
    if (!els.prepay || !els.prepayHint) return;
    const total = Math.max(0, roundMoney(orderTotal));
    const maxPrepay = maxPrepayAmount(total);
    els.prepay.max = String(maxPrepay);
    els.prepayHint.textContent =
      "Якщо отримувач вніс передплату, вкажіть суму для вирахування з накладеного платежу";
  }

  function selectedOwnTtnCarrier() {
    return (
      els.checkoutForm?.querySelector('input[name="ownTtnCarrier"]:checked')?.value ||
      "nova_poshta"
    );
  }

  function normalizeRmpNumber(raw) {
    let text = String(raw || "").trim().toUpperCase().replace(/\s+/g, "");
    if (!text) return "";
    text = text.replace(/^RMP-?/i, "");
    text = text.replace(/\D/g, "");
    return text ? `RMP-${text}` : "RMP-";
  }

  function syncOwnTtnCarrierUi() {
    const ownTtn = Boolean(els.ownTtn?.checked);
    if (els.ttnFields) els.ttnFields.classList.toggle("hidden", !ownTtn);
    if (els.recipientNameFields) els.recipientNameFields.classList.toggle("hidden", ownTtn);
    if (els.deliverySection) els.deliverySection.classList.toggle("hidden", ownTtn);
    if (els.phoneFieldLabel) {
      els.phoneFieldLabel.textContent = ownTtn ? "Номер телефону клієнта" : "Телефон";
    }
    if (!ownTtn) return;
    const carrier = selectedOwnTtnCarrier();
    const isNp = carrier === "nova_poshta";
    if (els.ttnNpBlock) els.ttnNpBlock.classList.toggle("hidden", !isNp);
    if (els.ttnRmpBlock) els.ttnRmpBlock.classList.toggle("hidden", isNp);
  }

  function syncPaymentAndTtn() {
    const allowCod = isFlagEnabled(dropperSettings.allow_cod, true);
    const allowBalance = Boolean(dropperSettings.allow_negative_balance);

    // Без наложенки від постачальника — лише власна ТТН
    if (!allowCod && els.ownTtn && !els.ownTtn.checked) {
      els.ownTtn.checked = true;
    }

    const ownTtn = Boolean(els.ownTtn?.checked);
    syncOwnTtnCarrierUi();

    const hideCod = ownTtn || !allowCod;
    if (els.codPaymentCard) {
      els.codPaymentCard.classList.toggle("hidden", hideCod);
      const codInput = els.codPaymentCard.querySelector('input[name="paymentMethod"]');
      if (codInput) {
        codInput.disabled = hideCod;
        if (hideCod) codInput.checked = false;
      }
    }
    if (els.codPaymentHint) {
      els.codPaymentHint.classList.toggle("hidden", hideCod);
    }
    if (els.balancePaymentCard) {
      els.balancePaymentCard.classList.toggle("hidden", !allowBalance);
      const balInput = els.balancePaymentCard.querySelector('input[name="paymentMethod"]');
      if (balInput) balInput.disabled = !allowBalance;
    }

    let payment = selectedPaymentMethod();
    if (hideCod && (payment === "cod" || !payment)) {
      const fallback = allowBalance
        ? els.checkoutForm.querySelector('input[name="paymentMethod"][value="balance"]')
        : els.checkoutForm.querySelector('input[name="paymentMethod"][value="requisites"]');
      if (fallback) {
        fallback.disabled = false;
        fallback.checked = true;
      }
      payment = selectedPaymentMethod();
    }
    if (!allowBalance && payment === "balance") {
      const req = els.checkoutForm.querySelector('input[name="paymentMethod"][value="requisites"]');
      if (req) {
        req.disabled = false;
        req.checked = true;
      }
      payment = selectedPaymentMethod();
    }

    const showRequisites = payment === "requisites";
    const showBalance = payment === "balance";
    const isCodPayment = !ownTtn && allowCod && payment === "cod";
    // Одне поле: для реквізитів/балансу — оціночна; для наложенки — сума НП (= Cost + COD)
    const showPaymentValue = !ownTtn;
    const showPrepayOnly = isCodPayment;

    if (els.estimatedCostBlock) {
      els.estimatedCostBlock.classList.toggle("hidden", !showPaymentValue);
    }
    if (isCodPayment) {
      if (els.estimatedCostLabel) {
        els.estimatedCostLabel.textContent = "Сума накладного платежу";
      }
      if (els.estimatedCost) {
        els.estimatedCost.placeholder = "Сума накладного платежу";
      }
      if (els.estimatedCostHint) {
        els.estimatedCostHint.textContent =
          "Оголошена вартість і накладений платіж для Нової Пошти (одна сума)";
      }
    } else {
      if (els.estimatedCostLabel) {
        els.estimatedCostLabel.textContent = "Оціночна вартість";
      }
      if (els.estimatedCost) {
        els.estimatedCost.placeholder = "Оціночна вартість посилки";
      }
      if (els.estimatedCostHint) {
        els.estimatedCostHint.textContent =
          "Для накладної Нової Пошти (оголошена вартість)";
      }
    }

    if (els.prepayBlock) els.prepayBlock.classList.toggle("hidden", !showPrepayOnly);
    if (els.prepayField) els.prepayField.classList.toggle("hidden", !showPrepayOnly);
    // Окреме поле наложенки не потрібне — сума в #estimatedCost
    if (els.codAmountField) {
      els.codAmountField.classList.add("hidden");
    }
    if (els.prepayHint) els.prepayHint.classList.toggle("hidden", !showPrepayOnly);

    els.requisitesBlock.classList.toggle("hidden", !showRequisites);
    if (els.balancePayHint) els.balancePayHint.classList.toggle("hidden", !showBalance);

    const total = cartMoneyTotal();
    if (els.estimatedCost && showPaymentValue && !els.estimatedCost.value) {
      els.estimatedCost.value = String(Math.max(1, Math.round(total)));
    }
    updatePrepayUi(total);
    updateRequisitesIntro(total);
    if (els.balancePayHint && showBalance) {
      const room = balanceSpendRoom();
      els.balancePayHint.textContent =
        `Суму «Дроп ціна» (${formatMoneyAmount(total)} грн) буде списано з балансу після отримання посилки клієнтом. ` +
        `Доступно з урахуванням ліміту мінусу (фактичний баланс): ${formatMoneyAmount(room)} грн.`;
    }
  }

  function stockNumber(stock) {
    if (stock === null || stock === undefined || stock === "") return null;
    const n = Number(stock);
    if (!Number.isFinite(n)) return null;
    return Math.max(0, Math.floor(n));
  }

  function stockLabel(stock) {
    const n = stockNumber(stock);
    if (n === null) {
      return `<span class="stock-ok">Наявність: —</span>`;
    }
    if (n <= 0) {
      return `<span class="stock-out">Немає в наявності</span>`;
    }
    return `<span class="stock-ok">В наявності: ${n}</span>`;
  }

  function locationLabel(location) {
    const loc = String(location || "").trim();
    if (!loc) return "";
    return `<span class="warehouse-loc">Розташування: <b>${escapeHtml(loc)}</b></span>`;
  }

  function availableQtyLabel(stock) {
    const n = stockNumber(stock);
    if (n === null) {
      return `<div class="stock-ok">Доступна кількість: —</div>`;
    }
    if (n <= 0) {
      return `<div class="stock-out">Доступна кількість: 0</div>`;
    }
    return `<div class="stock-ok">Доступна кількість: ${n}</div>`;
  }

  function clampQtyToStock(item, qty) {
    const next = Math.max(1, Number(qty) || 1);
    const max = stockNumber(item?.stock);
    if (max === null) return next;
    if (max <= 0) return 0;
    return Math.min(next, max);
  }

  function canAddMore(item, currentQty = 0) {
    const max = stockNumber(item?.stock);
    if (max === null) return true;
    return currentQty < max;
  }

  function closePhotoZoom() {
    document.querySelectorAll(".card-photo.is-zoomed").forEach((img) => {
      img.classList.remove("is-zoomed");
    });
    if (els.photoZoomBackdrop) {
      els.photoZoomBackdrop.classList.add("hidden");
    }
  }

  function togglePhotoZoom(img) {
    if (!img || !img.getAttribute("src")) return;
    const wasZoomed = img.classList.contains("is-zoomed");
    closePhotoZoom();
    if (!wasZoomed) {
      img.classList.add("is-zoomed");
      if (els.photoZoomBackdrop) {
        els.photoZoomBackdrop.classList.remove("hidden");
      }
    }
  }

  function isWarehouseCatalogMode() {
    return (
      sessionState.role === "warehouse" ||
      previewState.mode === "warehouse" ||
      Boolean(sessionState.warehouseCatalog)
    );
  }

  function renderCatalogCards(items, { showLocation = false, showAdd = true } = {}) {
    const cart = showAdd ? loadCart() : [];
    return items
      .map((item) => {
        const photo = item.photo_url || "";
        const inCart = showAdd
          ? cart.find((row) => cartKey(row) === cartKey(item))
          : null;
        const currentQty = inCart?.qty || 0;
        const outOfStock = stockNumber(item.stock) === 0;
        const atLimit = showAdd ? !canAddMore(item, currentQty) : true;
        const disabled = outOfStock || atLimit ? "disabled" : "";
        return `
          <article class="card">
            <img class="card-photo" src="${photo || ""}" alt="" draggable="false" onerror="this.style.opacity=0.2" />
            <div class="card-body">
              <div class="card-title">${escapeHtml(item.name || "")}</div>
              <div class="meta card-meta-line">
                <span>Код: <b>${escapeHtml(item.code || "")}</b> · ${escapeHtml(item.color || "без кольору")}</span>
                ${
                  item.live_photo_url
                    ? `<a class="live-photo-btn" href="${escapeHtml(item.live_photo_url)}" target="_blank" rel="noopener noreferrer">Додаткові фото</a>`
                    : ""
                }
              </div>
              <div class="row-actions">
                <div>
                  ${showAdd ? renderPriceHtml(item) : ""}
                  ${stockLabel(item.stock)}
                  ${showLocation ? locationLabel(item.location) : ""}
                </div>
                ${
                  showAdd
                    ? `<button class="icon-btn" data-add="${encodeURIComponent(
                        JSON.stringify(item)
                      )}" ${disabled} title="В кошик">🛒</button>`
                    : ""
                }
              </div>
            </div>
          </article>
        `;
      })
      .join("");
  }

  function renderResults(items) {
    closePhotoZoom();
    if (!items.length) {
      els.results.innerHTML = "";
      els.status.textContent = "Нічого не знайдено за цим кодом";
      return;
    }

    els.status.textContent = `Знайдено варіантів: ${items.length}`;
    els.results.innerHTML = renderCatalogCards(items, {
      showLocation: false,
      showAdd: true,
    });
  }

  function sanitizeCart(cart) {
    const next = [];
    for (const item of cart) {
      const qty = clampQtyToStock(item, item.qty || 1);
      if (qty <= 0) continue;
      next.push({ ...item, qty });
    }
    return next;
  }

  function renderCart() {
    closePhotoZoom();
    let cart = sanitizeCart(loadCart());
    saveCart(cart);

    if (!cart.length) {
      els.cartEmpty.classList.remove("hidden");
      els.cartList.innerHTML = "";
      els.cartFooter.classList.add("hidden");
      updateCartIndicators();
      return;
    }

    els.cartEmpty.classList.add("hidden");
    els.cartFooter.classList.remove("hidden");
    els.cartCount.textContent = String(cartQtyTotal(cart));
    els.cartSum.textContent = formatMoney(cartMoneyTotal(cart));

    els.cartList.innerHTML = cart
      .map((item, index) => {
        const photo = item.photo_url || "";
        const qty = item.qty || 1;
        const plusDisabled = canAddMore(item, qty) ? "" : "disabled";
        return `
          <article class="card">
            <img class="card-photo" src="${photo}" alt="" draggable="false" onerror="this.style.opacity=0.2" />
            <div class="card-body">
              <div class="card-title">${escapeHtml(item.name || "")}</div>
              <div class="meta">Код: <b>${escapeHtml(item.code || "")}</b> · ${escapeHtml(item.color || "без кольору")}</div>
              <div class="row-actions">
                <div>
                  ${renderPriceHtml(item)}
                  ${availableQtyLabel(item.stock)}
                </div>
                <div class="qty">
                  <button type="button" data-dec="${index}">−</button>
                  <strong>${qty}</strong>
                  <button type="button" data-inc="${index}" ${plusDisabled} title="${
                    plusDisabled ? "Немає більше в наявності" : "Додати"
                  }">+</button>
                  <button type="button" data-del="${index}" title="Видалити">✕</button>
                </div>
              </div>
            </div>
          </article>
        `;
      })
      .join("");
    updateCartIndicators();
  }

  function addToCart(item) {
    const max = stockNumber(item?.stock);
    if (max === 0) {
      showToast("Товару немає в наявності");
      return;
    }

    const cart = loadCart();
    const key = cartKey(item);
    const existing = cart.find((row) => cartKey(row) === key);
    const currentQty = existing?.qty || 0;

    if (!canAddMore(item, currentQty)) {
      showToast(`Доступно лише ${max} шт.`);
      return;
    }

    if (existing) {
      existing.qty = clampQtyToStock(item, currentQty + 1);
      if (item.stock !== undefined) existing.stock = item.stock;
    } else {
      cart.push({ ...item, qty: 1 });
    }
    saveCart(sanitizeCart(cart));
    showToast("Товар додано в кошик");
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function collectCheckoutData() {
    const form = els.checkoutForm;
    const deliveryMethod =
      form.querySelector('input[name="deliveryMethod"]:checked')?.value || "";
    const paymentMethod =
      form.querySelector('input[name="paymentMethod"]:checked')?.value || "";
    const ttnPdfFile = els.ttnPdf?.files?.[0] || null;
    const ownTtnNumber =
      selectedOwnTtnCarrier() === "rozetka"
        ? normalizeRmpNumber(form.rmpNumber?.value || "")
        : (form.ttnNumber?.value || "").replace(/\D/g, "");
    return {
      firstName: form.firstName.value.trim(),
      patronymic: form.patronymic.value.trim(),
      lastName: form.lastName.value.trim(),
      phone: form.phone.value.trim(),
      deliveryMethod,
      city: form.city.value.trim(),
      cityRef: form.cityRef.value.trim(),
      settlementRef: form.settlementRef.value.trim(),
      warehouse: form.warehouse.value.trim(),
      warehouseRef: form.warehouseRef.value.trim(),
      street: form.street.value.trim(),
      streetRef: form.streetRef.value.trim(),
      house: form.house.value.trim(),
      apartment: form.apartment.value.trim(),
      npCity: npState.city,
      npWarehouse: npState.warehouse,
      npStreet: npState.street,
      ownTtn: Boolean(form.ownTtn.checked),
      ownTtnCarrier: selectedOwnTtnCarrier(),
      estimatedCost: form.estimatedCost?.value?.trim() || "",
      ttnNumber: ownTtnNumber,
      rmpNumber: normalizeRmpNumber(form.rmpNumber?.value || ""),
      paymentMethod,
      codAmount: form.codAmount?.value?.trim() || "",
      prepay: form.prepay.value.trim(),
      comment: form.comment.value.trim(),
      rulesAccepted: Boolean(form.rulesAccepted.checked),
      receiptName: "",
      receiptFile: null,
      ttnPdfName: ttnPdfFile ? ttnPdfFile.name : "",
      ttnPdfFile,
      cart: loadCart(),
      total: cartMoneyTotal(),
    };
  }

  function validateCheckout(data) {
    if (!data.phone || !isPhoneComplete()) {
      return "Вкажіть повний телефон у форматі +380(XX)XXX-XX-XX";
    }
    if (phoneBlacklisted) {
      return (
        "Клієнт у чорному списку. Відправка неможлива. Зверніться до постачальника."
      );
    }

    if (data.ownTtn) {
      data.firstName = "";
      data.patronymic = "";
      data.lastName = "";
      data.deliveryMethod = "own_ttn";
      data.city = "";
      data.cityRef = "";
      data.settlementRef = "";
      data.warehouse = "";
      data.warehouseRef = "";
      data.street = "";
      data.streetRef = "";
      data.house = "";
      data.apartment = "";
      data.npCity = null;
      data.npWarehouse = null;
      data.npStreet = null;

      if (data.paymentMethod !== "requisites" && data.paymentMethod !== "balance") {
        return "При власній ТТН доступна оплата на реквізити або з балансу";
      }
      const carrier = data.ownTtnCarrier || "nova_poshta";
      if (carrier === "rozetka") {
        const rmp = normalizeRmpNumber(data.rmpNumber || "");
        if (!/^RMP-\d{6,20}$/i.test(rmp)) {
          return "Вкажіть номер RMP у форматі RMP-XXXXXXXXX";
        }
        data.rmpNumber = rmp.toUpperCase();
        data.ttnNumber = data.rmpNumber;
        data.ownTtnCarrier = "rozetka";
      } else {
        if (!data.ttnNumber) return "Вкажіть номер ТТН";
        if (!/^\d+$/.test(data.ttnNumber)) {
          return "Номер ТТН має містити лише цифри";
        }
        if (data.ttnNumber.length < 10) {
          return "Вкажіть повний номер ТТН";
        }
        data.ownTtnCarrier = "nova_poshta";
      }
      if (!data.ttnPdfFile) {
        return "Прикріпіть файл PDF 100×100";
      }
      const pdfName = (data.ttnPdfFile.name || "").toLowerCase();
      const pdfType = data.ttnPdfFile.type || "";
      if (pdfType && pdfType !== "application/pdf" && !pdfName.endsWith(".pdf")) {
        return "Файл 100×100 має бути у форматі PDF";
      }
      if (!pdfName.endsWith(".pdf")) {
        return "Файл 100×100 має бути у форматі PDF";
      }
    } else {
      if (!data.firstName) return "Вкажіть ім'я отримувача";
      if (!data.lastName) return "Вкажіть прізвище отримувача";
      if (!data.cityRef || !npState.city) {
        return "Оберіть населений пункт зі списку Нової Пошти";
      }
      if (data.deliveryMethod === "np_warehouse" && (!data.warehouseRef || !npState.warehouse)) {
        return "Оберіть відділення/поштомат зі списку Нової Пошти";
      }
      if (data.deliveryMethod === "np_courier") {
        if (!data.patronymic) return "Для курʼєра вкажіть по батькові";
        if (!data.streetRef || !npState.street) {
          return "Оберіть вулицю зі списку Нової Пошти";
        }
        if (!data.house) return "Вкажіть номер будинку";
      }
      if (!isFlagEnabled(dropperSettings.allow_cod, true)) {
        return "Відправлення накладним платежем заблоковано постачальником";
      }
      const estRaw = data.estimatedCost === "" ? null : Number(data.estimatedCost);
      if (estRaw === null || Number.isNaN(estRaw) || estRaw < 1) {
        return data.paymentMethod === "cod"
          ? "Вкажіть суму накладного платежу (мін. 1 ₴)"
          : "Вкажіть оціночну вартість (мін. 1 ₴)";
      }
      data.estimatedCost = Math.round(estRaw);
      if (data.paymentMethod === "cod") {
        // Одна сума = оголошена вартість НП + накладений платіж
        data.codAmount = String(data.estimatedCost);
      }
    }

    if (!data.rulesAccepted) {
      return "Підтвердіть ознайомлення з правилами";
    }

    if (!data.ownTtn && !isFlagEnabled(dropperSettings.allow_cod, true)) {
      return "Відправлення накладним платежем заблоковано постачальником";
    }

    if (data.paymentMethod === "cod" && !isFlagEnabled(dropperSettings.allow_cod, true)) {
      return "Передачу замовлень наложкою для вас вимкнено";
    }

    if (data.paymentMethod === "balance") {
      if (!dropperSettings.allow_negative_balance) {
        return "Оплата з балансу для вас вимкнена";
      }
      const room = balanceSpendRoom();
      const total = roundMoney(data.total || 0);
      if (total > room + 0.01) {
        return (
          `Недостатньо доступного балансу (потрібно ${formatMoneyAmount(total)} грн, ` +
          `доступно ${formatMoneyAmount(room)} грн)`
        );
      }
      data.codAmount = 0;
      data.prepay = "";
      data.prepayBalanceDebit = total;
    } else if (!data.ownTtn && data.paymentMethod === "cod") {
      // Сума вже з поля estimatedCost (= наложка + оціночна)
      const codRaw =
        data.codAmount === "" || data.codAmount == null
          ? Number(data.estimatedCost)
          : Number(data.codAmount);
      if (Number.isNaN(codRaw) || codRaw < 1) {
        return "Вкажіть суму накладного платежу";
      }
      data.codAmount = Math.round(codRaw);
      data.estimatedCost = data.codAmount;

      const prepay = data.prepay === "" ? 0 : Number(data.prepay);
      if (Number.isNaN(prepay) || prepay < 0) {
        return "Некоректна сума передплати";
      }
      if (prepay > data.codAmount) {
        return "Передплата не може перевищувати суму накладного платежу";
      }
      const maxPrepay = maxPrepayAmount(data.total);
      if (prepay > maxPrepay) {
        if (dropperSettings.allow_negative_balance) {
          return `Передплата не може перевищувати ${Math.round(maxPrepay)} грн (Дроп ціна + доступний баланс)`;
        }
        return `Передплата не може перевищувати ${Math.round(data.total)} грн`;
      }
      data.prepayBalanceDebit = Math.max(
        0,
        roundMoney(prepay - Number(data.total || 0))
      );
    } else {
      data.codAmount = 0;
      data.prepayBalanceDebit = 0;
    }
    return "";
  }

  function paymentMethodLabel(value) {
    if (value === "cod") return "Оплата при отриманні";
    if (value === "requisites") return "Оплата на реквізити";
    if (value === "balance") return "З балансу";
    return value || "—";
  }

  function deliveryMethodLabel(value) {
    if (value === "np_warehouse") return "Відділення / поштомат НП";
    if (value === "np_courier") return "Курʼєр НП";
    if (value === "own_ttn") return "За ТТН дроппера";
    return value || "—";
  }

  function formatOrderDate(iso) {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return iso;
      return d.toLocaleString("uk-UA", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  }

  function renderConfirmSummary(data) {
    if (!els.confirmSummary) return;
    const cartLines = (data.cart || [])
      .map((item) => {
        const qty = item.qty || 1;
        const head = `${item.code || ""} — ${item.name || ""} × ${qty}`;
        if (hasDiscountPrice(item)) {
          return `${head} · <span class="price-old-inline">${escapeHtml(
            String(item.drop_price_original)
          )} ₴</span> <b>${escapeHtml(String(item.drop_price))} ₴</b>`;
        }
        return `${head} · ${escapeHtml(String(item.drop_price || "—"))} ₴`;
      })
      .join("<br/>");
    const deliveryExtra =
      data.deliveryMethod === "np_courier"
        ? `${data.street || ""}, буд. ${data.house || ""}${
            data.apartment ? `, кв. ${data.apartment}` : ""
          }`
        : data.warehouse || "";
    const debit = roundMoney(data.prepayBalanceDebit || 0);
    const totalExact = roundMoney(data.total || 0);
    const showClassicCod = data.paymentMethod === "cod";
    const codExact = showClassicCod ? roundMoney(data.codAmount || 0) : 0;
    const prepayExact = showClassicCod
      ? roundMoney(data.prepay === "" ? 0 : data.prepay || 0)
      : 0;
    const dropperProfit = showClassicCod
      ? roundMoney(codExact - prepayExact - totalExact)
      : null;
    const estExact = !data.ownTtn ? roundMoney(data.estimatedCost || 0) : 0;
    const recipientBlock = data.ownTtn
      ? `<div class="confirm-block">
        <div class="confirm-label">Клієнт</div>
        <div class="confirm-value">${escapeHtml(data.phone)}</div>
      </div>`
      : `<div class="confirm-block">
        <div class="confirm-label">Отримувач</div>
        <div class="confirm-value">${escapeHtml(
          `${data.lastName} ${data.firstName} ${data.patronymic || ""}`.trim()
        )}\n${escapeHtml(data.phone)}</div>
      </div>
      <div class="confirm-block">
        <div class="confirm-label">Доставка</div>
        <div class="confirm-value">${escapeHtml(deliveryMethodLabel(data.deliveryMethod))}
${escapeHtml(data.city || "")}
${escapeHtml(deliveryExtra)}</div>
      </div>`;
    const paymentExtra = showClassicCod
      ? `Накладений платіж / оціночна: ${escapeHtml(formatMoneyAmount(codExact))} ₴\nПередплата: ${escapeHtml(formatMoneyAmount(prepayExact))} ₴\nПрибуток дроппера: ${escapeHtml(formatMoneyAmount(dropperProfit))} ₴`
      : estExact > 0
        ? `Оціночна вартість: ${escapeHtml(formatMoneyAmount(estExact))} ₴`
        : "";
    const ttnLine = data.ownTtn
      ? data.ownTtnCarrier === "rozetka"
        ? `Власний RMP: ${escapeHtml(data.ttnNumber || data.rmpNumber || "")}`
        : `Власна ТТН НП: ${escapeHtml(data.ttnNumber || "")}`
      : "ТТН: створиться пізніше (НП)";
    els.confirmSummary.innerHTML = `
      ${recipientBlock}
      <div class="confirm-block">
        <div class="confirm-label">Оплата</div>
        <div class="confirm-value">${escapeHtml(paymentMethodLabel(data.paymentMethod))}
Дроп ціна: ${escapeHtml(formatMoneyAmount(totalExact))} ₴
${paymentExtra}
${debit > 0 ? `З балансу спишеться після отримання: ${escapeHtml(formatMoneyAmount(debit))} ₴` : ""}
${ttnLine}</div>
      </div>
      <div class="confirm-block">
        <div class="confirm-label">Товари</div>
        <div class="confirm-value confirm-value-html">${cartLines}</div>
      </div>
      ${
        data.comment
          ? `<div class="confirm-block"><div class="confirm-label">Коментар</div><div class="confirm-value">${escapeHtml(
              data.comment
            )}</div></div>`
          : ""
      }
    `;
  }

  function openConfirmView(data) {
    checkoutDraft = data;
    els.checkoutView.classList.add("hidden");
    if (els.confirmView) els.confirmView.classList.remove("hidden");
    renderConfirmSummary(data);
    if (els.confirmError) {
      els.confirmError.classList.add("hidden");
      els.confirmError.textContent = "";
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
      if (!file) {
        reject(new Error("Файл не обрано"));
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const result = String(reader.result || "");
        const idx = result.indexOf(",");
        resolve(idx >= 0 ? result.slice(idx + 1) : result);
      };
      reader.onerror = () => reject(new Error("Не вдалося прочитати файл"));
      reader.readAsDataURL(file);
    });
  }

  function buildOrderApiPayload(data) {
    const ownTtn = Boolean(data.ownTtn);
    return {
      chat_id: effectiveDropperChatId(),
      user_id: currentTelegramUser().user_id,
      first_name: ownTtn ? "" : data.firstName,
      patronymic: ownTtn ? "" : data.patronymic || "",
      last_name: ownTtn ? "" : data.lastName,
      phone: data.phone,
      delivery_method: ownTtn ? "own_ttn" : data.deliveryMethod,
      city: ownTtn ? "" : data.city || "",
      city_ref: ownTtn ? "" : data.cityRef || "",
      settlement_ref: ownTtn ? "" : data.settlementRef || "",
      warehouse: ownTtn ? "" : data.warehouse || "",
      warehouse_ref: ownTtn ? "" : data.warehouseRef || "",
      street: ownTtn ? "" : data.street || "",
      street_ref: ownTtn ? "" : data.streetRef || "",
      house: ownTtn ? "" : data.house || "",
      apartment: ownTtn ? "" : data.apartment || "",
      own_ttn: ownTtn,
      own_ttn_carrier: ownTtn ? data.ownTtnCarrier || "nova_poshta" : "",
      ttn_number: data.ttnNumber || "",
      payer_type: "Recipient",
      estimated_cost: Number(data.estimatedCost || 0),
      payment_method: data.paymentMethod,
      prepay: data.prepay === "" ? 0 : Number(data.prepay || 0),
      cod_amount: Number(data.codAmount || 0),
      comment: data.comment || "",
      receipt_name: data.receiptName || "",
      ttn_pdf_name: data.ttnPdfName || "",
      ttn_pdf_base64: data.ttnPdfBase64 || "",
      cart: (data.cart || []).map((item) => ({
        product_id: item.product_id || "",
        code: item.code || "",
        name: item.name || "",
        color: item.color || "",
        qty: item.qty || 1,
        drop_price: item.drop_price || "",
        drop_price_original: item.drop_price_original || "",
        extra_discount_percent: item.extra_discount_percent || 0,
        stock: item.stock,
        photo_url: item.photo_url || "",
      })),
      total: Number(data.total || 0),
      np_city: ownTtn ? null : data.npCity || null,
      np_warehouse: ownTtn ? null : data.npWarehouse || null,
      np_street: ownTtn ? null : data.npStreet || null,
    };
  }

  async function submitOrder() {
    if (!checkoutDraft) return;
    if (isOwnerRolePreview()) {
      showToast("Режим перегляду — замовлення не створюється");
      if (els.confirmError) {
        els.confirmError.textContent = "Режим перегляду — замовлення не створюється";
        els.confirmError.classList.remove("hidden");
      }
      return;
    }
    if (els.confirmSubmit) els.confirmSubmit.disabled = true;
    if (els.confirmError) {
      els.confirmError.classList.add("hidden");
      els.confirmError.textContent = "";
    }
    try {
      if (checkoutDraft.ownTtn && checkoutDraft.ttnPdfFile) {
        checkoutDraft.ttnPdfBase64 = await readFileAsBase64(checkoutDraft.ttnPdfFile);
      }
      const response = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildOrderApiPayload(checkoutDraft)),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof result.detail === "string" ? result.detail : "Не вдалося створити замовлення"
        );
      }
      saveCart([]);
      updateCartIndicators();
      checkoutDraft = null;
      const orderNo = result.order?.order_number || "";
      showToast(orderNo ? `Замовлення ${orderNo} прийнято` : "Замовлення прийнято");
      safeTgAlert(
        orderNo
          ? `Замовлення ${orderNo} прийнято. Деталі — у вкладці «Історія».`
          : "Замовлення прийнято."
      );
      if (els.confirmView) els.confirmView.classList.add("hidden");
      switchTab("history");
    } catch (error) {
      if (els.confirmError) {
        els.confirmError.textContent = error.message || "Помилка";
        els.confirmError.classList.remove("hidden");
      }
      showToast(error.message || "Помилка відправки");
    } finally {
      if (els.confirmSubmit) els.confirmSubmit.disabled = false;
    }
  }

  function orderPaymentMethod(order) {
    return (
      order.payment_method ||
      (order.payload && order.payload.payment && order.payload.payment.method) ||
      ""
    );
  }

  function orderCodAmount(order) {
    if (order.cod_amount != null && order.cod_amount !== "") {
      return roundMoney(order.cod_amount);
    }
    const pay = (order.payload && order.payload.payment) || {};
    return roundMoney(pay.cod_amount || 0);
  }

  function orderDropperProfit(order) {
    if (orderPaymentMethod(order) !== "cod") return null;
    const payload = order.payload || {};
    const ttn = String(order.ttn_status || "");
    if (
      ttn === "returned" ||
      ttn === "refused" ||
      ttn === "return_at_warehouse" ||
      payload.return_delivery_debited
    ) {
      return null;
    }
    const cod = orderCodAmount(order);
    const prepay = roundMoney(order.prepay || 0);
    const total = roundMoney(order.total || 0);
    return roundMoney(cod - prepay - total);
  }

  function daysWordUk(n) {
    const abs = Math.abs(Number(n) || 0);
    const mod10 = abs % 10;
    const mod100 = abs % 100;
    if (mod10 === 1 && mod100 !== 11) return "день";
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "дні";
    return "днів";
  }

  function daysAtWarehouse(order) {
    const raw = (order.payload || {}).np_at_warehouse_at;
    if (!raw) return null;
    const start = new Date(raw).getTime();
    if (!Number.isFinite(start)) return null;
    return Math.max(0, Math.floor((Date.now() - start) / 86400000));
  }

  /** Вкладка історії: awaiting | transit | received | returns */
  function orderHistoryBucket(order) {
    const payload = order.payload || {};
    const ret = payload.dropper_return;
    const ttn = String(order.ttn_status || "");
    if (ret && typeof ret === "object") return "returns";
    if (
      ttn === "returned" ||
      ttn === "refused" ||
      ttn === "return_at_warehouse" ||
      ttn === "cancelled" ||
      payload.return_at_warehouse ||
      String(order.status || "") === "cancelled"
    ) {
      return "returns";
    }
    if (ttn === "received") return "received";
    if (ttn === "in_transit" || ttn === "at_warehouse" || ttn === "provided") {
      return "transit";
    }
    // pending_create / created / create_error / none / ще без руху НП
    return "awaiting";
  }

  function dropperReturnTypeLabel(type) {
    return String(type || "") === "easy" ? "Легке повернення" : "Звичайне повернення";
  }

  function dropperReturnStatusLabel(status) {
    const st = String(status || "");
    if (st === "accepted" || st === "closed") return "Закрито";
    if (st === "awaiting_confirm") return "Очікує підтвердження";
    if (st === "awaiting_receipt" || st === "pending") return "Очікує отримання";
    return "Очікує обробки";
  }

  function normalizeReturnStatus(status) {
    const st = String(status || "");
    if (st === "pending") return "awaiting_receipt";
    if (st === "closed") return "accepted";
    return st || "awaiting_receipt";
  }

  function orderHistoryStatus(order) {
    const payload = order.payload || {};
    const ttn = String(order.ttn_status || "");
    const hasTtn = Boolean(order.ttn_number || payload.ttn_number);
    const ret = payload.dropper_return;

    if (ret && typeof ret === "object") {
      const st = normalizeReturnStatus(ret.status);
      if (st === "accepted") {
        return {
          kind: "return_accepted",
          label: "Повернення підтверджено",
          sub: dropperReturnTypeLabel(ret.type),
        };
      }
      if (st === "awaiting_confirm") {
        return {
          kind: "return_pending",
          label: "Очікує підтвердження",
          sub: dropperReturnTypeLabel(ret.type),
        };
      }
      return {
        kind: "return_pending",
        label: "Очікує отримання",
        sub: dropperReturnTypeLabel(ret.type),
      };
    }
    if (payload.return_at_warehouse || ttn === "return_at_warehouse") {
      return { kind: "return_warehouse", label: "Отримано повернення на склад", sub: "" };
    }
    if (String(order.status || "") === "cancelled" || ttn === "cancelled") {
      return { kind: "refused", label: "Скасовано", sub: "" };
    }
    if (
      payload.return_after_received ||
      (ttn === "returned" && (payload.ever_received || payload.profit_reversed))
    ) {
      return { kind: "returned", label: "Повернено", sub: "" };
    }
    if (ttn === "refused" || ttn === "returned") {
      return { kind: "refused", label: "Відмова", sub: "" };
    }
    if (ttn === "received") {
      return { kind: "received", label: "Отримано", sub: "" };
    }
    if (ttn === "at_warehouse") {
      const days = daysAtWarehouse(order);
      const sub =
        days == null ? "" : `На відділенні: ${days} ${daysWordUk(days)}`;
      return { kind: "warehouse", label: "Прибуло до відділення", sub };
    }
    if (ttn === "in_transit") {
      return { kind: "transit", label: "В дорозі", sub: "" };
    }
    // Прийнято: заказ принят ботом (с ТТН / своей накладной / ещё создаётся)
    if (
      String(order.status || "") === "accepted" ||
      hasTtn ||
      ["created", "provided", "pending_create", "create_error", "none"].includes(ttn)
    ) {
      return { kind: "accepted", label: "Прийнято", sub: "" };
    }
    return { kind: "other", label: String(order.status || "—"), sub: "" };
  }

  function renderOrderDetailsHtml(order, options = {}) {
    const payload = order.payload || {};
    const recipient = payload.recipient || {};
    const delivery = payload.delivery || {};
    const payment = payload.payment || {};
    const cart = payload.cart || [];
    const name = [recipient.last_name, recipient.first_name, recipient.patronymic]
      .filter(Boolean)
      .join(" ");
    const method = orderPaymentMethod(order);
    const ownTtn = Boolean(order.own_ttn || payload.own_ttn);
    const ownCarrier = payload.own_ttn_carrier || "";
    const deliveryExtra =
      (order.delivery_method || delivery.method) === "np_courier"
        ? `${delivery.street || ""}, буд. ${delivery.house || ""}${
            delivery.apartment ? `, кв. ${delivery.apartment}` : ""
          }`
        : delivery.warehouse || "";
    const cartLines = cart
      .map((item) => {
        const qty = item.qty || 1;
        const head = `${item.code || ""} — ${item.name || ""} × ${qty}`;
        if (hasDiscountPrice(item)) {
          return `${head} · <span class="price-old-inline">${escapeHtml(
            String(item.drop_price_original)
          )} ₴</span> <b>${escapeHtml(String(item.drop_price))} ₴</b>`;
        }
        return `${head} · ${escapeHtml(String(item.drop_price || "—"))} ₴`;
      })
      .join("<br/>");
    const profit = orderDropperProfit(order);
    const debit = roundMoney(
      order.prepay_balance_debit != null
        ? order.prepay_balance_debit
        : payment.prepay_balance_debit || 0
    );
    const recipientHtml = ownTtn
      ? `<div class="confirm-block">
          <div class="confirm-label">Клієнт</div>
          <div class="confirm-value">${escapeHtml(recipient.phone || "—")}</div>
        </div>`
      : `<div class="confirm-block">
          <div class="confirm-label">Отримувач</div>
          <div class="confirm-value">${escapeHtml(name || "—")}\n${escapeHtml(
            recipient.phone || ""
          )}</div>
        </div>
        <div class="confirm-block">
          <div class="confirm-label">Доставка</div>
          <div class="confirm-value">${escapeHtml(
            deliveryMethodLabel(order.delivery_method || delivery.method || "")
          )}
${escapeHtml(delivery.city || "")}
${escapeHtml(deliveryExtra)}</div>
        </div>`;
    return `
      <div class="order-details-grid">
        ${recipientHtml}
        <div class="confirm-block">
          <div class="confirm-label">Оплата</div>
          <div class="confirm-value">${escapeHtml(paymentMethodLabel(method))}
Дроп ціна: ${escapeHtml(formatMoneyAmount(order.total || 0))} ₴
${
  method === "cod" &&
  !(
    payload.return_delivery_debited ||
    order.ttn_status === "returned" ||
    order.ttn_status === "refused" ||
    order.ttn_status === "return_at_warehouse"
  )
    ? `Накладений платіж: ${escapeHtml(formatMoneyAmount(orderCodAmount(order)))} ₴\nПередплата: ${escapeHtml(formatMoneyAmount(order.prepay || 0))} ₴\nПрибуток: ${escapeHtml(formatMoneyAmount(profit || 0))} ₴`
    : ""
}
${
  payload.return_delivery_debited
    ? `Відмова/повернення · доставка з балансу: −${escapeHtml(
        formatMoneyAmount(payload.return_delivery_cost || payload.np_delivery_cost || 0)
      )} ₴`
    : ""
}
${debit > 0 ? `З балансу: ${escapeHtml(formatMoneyAmount(debit))} ₴` : ""}
${
  ownTtn
    ? ownCarrier === "rozetka"
      ? `Власний RMP: ${escapeHtml(order.ttn_number || payload.ttn_number || "")}`
      : `Власна ТТН НП: ${escapeHtml(order.ttn_number || payload.ttn_number || "")}`
    : escapeHtml(ttnStatusLabel(order))
}</div>
        </div>
        <div class="confirm-block">
          <div class="confirm-label">Товари</div>
          <div class="confirm-value confirm-value-html">${cartLines || "—"}</div>
        </div>
        ${
          payload.comment
            ? `<div class="confirm-block"><div class="confirm-label">Коментар</div><div class="confirm-value">${escapeHtml(
                payload.comment
              )}</div></div>`
            : ""
        }
        ${
          options.editable && payload.correction_request
            ? `<div class="confirm-block">
                <div class="confirm-label">Запит дроппера на виправлення</div>
                <div class="confirm-value">${escapeHtml(payload.correction_request)}</div>
              </div>`
            : ""
        }
        ${renderOrderTrackingTimelineHtml(order)}
        ${renderOrderChangesTimelineHtml(order)}
        ${renderOrderReturnBlockHtml(order, options)}
        ${
          options.allowDropperEdit
            ? renderOrderDropperActionsHtml(order, options)
            : ""
        }
        ${
          options.editable
            ? `<div class="order-edit-actions">
                <p class="hint">ТТН буде перестворено лише якщо ще очікує відправки.</p>
                <button type="button" class="btn primary" data-order-edit-open="${escapeHtml(
                  String(order.id || "")
                )}" data-order-edit-mode="${escapeHtml(options.editMode || "owner")}">Редагувати</button>
                <div class="order-edit-panel hidden" data-order-edit-panel="${escapeHtml(
                  String(order.id || "")
                )}"></div>
              </div>`
            : ""
        }
      </div>
    `;
  }

  function renderOrderReturnBlockHtml(order, options = {}) {
    const payload = order.payload || {};
    const ret = payload.dropper_return;
    const ttn = String(order.ttn_status || "");
    const canRequest =
      Boolean(options.dropperActions) &&
      ttn === "received" &&
      !(ret && typeof ret === "object");

    let infoHtml = "";
    if (ret && typeof ret === "object") {
      const st = normalizeReturnStatus(ret.status);
      infoHtml = `
        <div class="confirm-block">
          <div class="confirm-label">Заявка на повернення</div>
          <div class="confirm-value">${escapeHtml(dropperReturnTypeLabel(ret.type))}
Статус: ${escapeHtml(dropperReturnStatusLabel(st))}
ТТН повернення: ${escapeHtml(ret.ttn_number || "—")}
${ret.created_at ? `Створено: ${escapeHtml(formatOrderDate(ret.created_at) || ret.created_at)}` : ""}
${
  ret.accepted_at
    ? `Підтверджено: ${escapeHtml(formatOrderDate(ret.accepted_at) || ret.accepted_at)}`
    : ""
}</div>
        </div>`;
    }

    if (!canRequest) return infoHtml;

    return `
      ${infoHtml}
      <div class="order-edit-actions order-return-actions">
        <button type="button" class="btn primary" data-order-return-open="${escapeHtml(
          String(order.id || "")
        )}">Оформити повернення</button>
        <div class="order-return-form hidden" data-order-return-form="${escapeHtml(
          String(order.id || "")
        )}">
          <p class="hint" style="margin:0">
            Вкажіть номер зворотної ТТН: Нова Пошта (14+ цифр) або Rozetka (RMP-…).
          </p>
          <label class="field">
            <span class="field-label">ТТН повернення <span class="req">*</span></span>
            <input type="text" data-return-ttn placeholder="2045… або RMP-…" autocomplete="off" />
          </label>
          <div class="choice-list" role="radiogroup" aria-label="Тип повернення">
            <label class="choice-card">
              <input type="radio" name="returnType-${escapeHtml(String(order.id || ""))}" value="regular" checked />
              <span class="choice-body">
                <span class="choice-title">Звичайне повернення</span>
                <span class="choice-sub">На дані постачальника</span>
              </span>
            </label>
            <label class="choice-card">
              <input type="radio" name="returnType-${escapeHtml(String(order.id || ""))}" value="easy" />
              <span class="choice-body">
                <span class="choice-title">Легке повернення</span>
                <span class="choice-sub">Без заміни даних постачальника</span>
              </span>
            </label>
          </div>
          <p class="form-error hidden" data-return-error></p>
          <div class="order-edit-actions-row">
            <button type="button" class="btn primary" data-order-return-submit="${escapeHtml(
              String(order.id || "")
            )}">Відправити заявку</button>
            <button type="button" class="btn secondary" data-order-return-cancel="${escapeHtml(
              String(order.id || "")
            )}">Скасувати</button>
          </div>
        </div>
      </div>`;
  }

  function validateReturnTtn(raw) {
    const value = String(raw || "").trim().toUpperCase();
    if (!value) return { ok: false, message: "Вкажіть ТТН повернення" };
    if (/^RMP-\d{6,20}$/i.test(value)) {
      return { ok: true, ttn: value };
    }
    const digits = value.replace(/\D/g, "");
    if (digits.length >= 10) {
      return { ok: true, ttn: digits };
    }
    return {
      ok: false,
      message: "ТТН: Нова Пошта (мінімум 10 цифр) або Rozetka у форматі RMP-XXXXXXXXX",
    };
  }

  function renderOrderDropperActionsHtml(order, options = {}) {
    if (!options.allowDropperEdit) return "";
    if (String(order.status || "") === "cancelled") {
      return `<div class="order-edit-actions"><p class="hint">Замовлення скасовано</p></div>`;
    }
    const canModify = order.can_modify !== false;
    if (!canModify) {
      return `<div class="order-edit-actions"><p class="hint">Замовлення вже в дорозі — зміни недоступні</p></div>`;
    }
    const locked = Boolean(options.editWindow?.locked);
    if (locked) {
      return `
        <div class="order-edit-actions">
          <p class="hint">${escapeHtml(
            options.editWindow?.message ||
              "Зараз 11:50–14:30 — редагування закрите. Можна подати запит власнику."
          )}</p>
          <label class="field">
            <span class="field-label">Що потрібно виправити</span>
            <textarea data-correction-text rows="2" placeholder="Опишіть правки…"></textarea>
          </label>
          <button type="button" class="btn primary" data-order-correction-request="${escapeHtml(
            String(order.id || "")
          )}">Подати запит на виправлення</button>
        </div>`;
    }
    const allowCod = isFlagEnabled(dropperSettings.allow_cod, true);
    const editHint = allowCod
      ? "До 11:50 і після 14:30 (Київ) можна змінити або скасувати, якщо ще не відправлено. ТТН перествориться автоматично."
      : "До 11:50 і після 14:30 (Київ) можна змінити або скасувати, якщо ще не відправлено.";
    return `
      <div class="order-edit-actions">
        <p class="hint">${escapeHtml(editHint)}</p>
        <div class="order-edit-actions-row">
          <button type="button" class="btn primary" data-order-edit-open="${escapeHtml(
            String(order.id || "")
          )}" data-order-edit-mode="dropper">Редагувати</button>
          <button type="button" class="btn danger" data-order-cancel="${escapeHtml(
            String(order.id || "")
          )}">Скасувати замовлення</button>
        </div>
        <div class="order-edit-panel hidden" data-order-edit-panel="${escapeHtml(
          String(order.id || "")
        )}"></div>
      </div>`;
  }

  function formatChangeFieldLabel(field) {
    const map = {
      payment_method: "Оплата",
      delivery_method: "Доставка",
      own_ttn: "Власна ТТН",
      total: "Дроп ціна",
      prepay: "Передплата",
      prepay_balance_debit: "Списання з балансу",
      cod_amount: "Накладний платіж",
      ttn_number: "ТТН",
      ttn_status: "Статус ТТН",
      comment: "Коментар",
      cart: "Склад замовлення",
      "recipient.phone": "Телефон",
      "recipient.first_name": "Імʼя",
      "recipient.last_name": "Прізвище",
      "recipient.patronymic": "По батькові",
      "delivery.city": "Місто",
      "delivery.warehouse": "Відділення",
      "delivery.street": "Вулиця",
      "delivery.house": "Будинок",
      "delivery.apartment": "Квартира",
    };
    return map[field] || field;
  }

  function renderOrderTrackingTimelineHtml(order) {
    const payload = order.payload || {};
    const events = Array.isArray(payload.tracking_events) ? payload.tracking_events : [];
    let rows = events.slice().reverse();
    if (!rows.length && (payload.np_status_text || order.ttn_status)) {
      rows = [
        {
          at: payload.np_tracked_at || order.updated_at || "",
          status_text: payload.np_status_text || "",
          ttn_status: order.ttn_status || "",
          status_code: payload.np_status_code || "",
        },
      ];
    }
    if (!rows.length) {
      return `<div class="confirm-block">
        <div class="confirm-label">Історія доставки</div>
        <div class="confirm-value hint">Поки немає подій відстеження</div>
      </div>`;
    }
    const statusMap = {
      created: "створено / очікує відправки",
      in_transit: "в дорозі",
      at_warehouse: "у відділенні",
      received: "отримано",
      refused: "відмова",
      returned: "повернено",
      return_at_warehouse: "повернення на складі",
      failed: "помилка",
      pending_create: "створюється",
    };
    const items = rows
      .map((ev) => {
        const st = ev.ttn_status || "";
        const label =
          (ev.status_text || "").trim() ||
          statusMap[st] ||
          st ||
          "статус";
        const when = ev.at ? formatOrderDate(ev.at) : "—";
        return `<li class="order-timeline-item">
          <div class="order-timeline-time">${escapeHtml(when)}</div>
          <div class="order-timeline-body">${escapeHtml(label)}${
          ev.status_code ? ` <span class="meta">(код ${escapeHtml(String(ev.status_code))})</span>` : ""
        }</div>
        </li>`;
      })
      .join("");
    return `<div class="confirm-block">
      <div class="confirm-label">Історія доставки</div>
      <ul class="order-timeline">${items}</ul>
    </div>`;
  }

  function renderOrderChangesTimelineHtml(order) {
    const changes = Array.isArray(order.changes) ? order.changes : [];
    if (!changes.length) {
      return `<div class="confirm-block">
        <div class="confirm-label">Історія змін</div>
        <div class="confirm-value hint">Змін ще не було</div>
      </div>`;
    }
    const items = changes
      .map((ch) => {
        const who = ch.actor_label || ch.actor_role || "система";
        const when = ch.created_at ? formatOrderDate(ch.created_at) : "—";
        const diff = Array.isArray(ch.diff) ? ch.diff : [];
        const detail =
          ch.summary ||
          diff
            .slice(0, 6)
            .map((d) => {
              if (d.field === "cart") return "Склад замовлення: змінено";
              return `${formatChangeFieldLabel(d.field)}: ${d.old || "—"} → ${d.new || "—"}`;
            })
            .join("\n");
        return `<li class="order-timeline-item">
          <div class="order-timeline-time">${escapeHtml(when)}</div>
          <div class="order-timeline-body"><b>${escapeHtml(who)}</b>
            <div class="order-timeline-diff">${escapeHtml(detail)}</div>
          </div>
        </li>`;
      })
      .join("");
    return `<div class="confirm-block">
      <div class="confirm-label">Історія змін</div>
      <ul class="order-timeline">${items}</ul>
    </div>`;
  }

  function ttnStatusLabel(order) {
    const status = String(order?.ttn_status || "");
    const number = order?.ttn_number || (order?.payload && order.payload.ttn_number) || "";
    const text = (order?.payload && order.payload.np_status_text) || "";
    if (number) {
      const map = {
        created: "створено",
        in_transit: "в дорозі",
        at_warehouse: "у відділенні",
        received: "отримано",
        refused: "відмова",
        returned: "повернено",
        return_at_warehouse: "повернення на складі",
        failed: "помилка",
        provided: "власна ТТН",
      };
      const st = map[status] || status || "трекінг";
      return `ТТН: ${number}${st ? ` · ${st}` : ""}${text && !map[status] ? ` (${text})` : ""}`;
    }
    if (status === "create_error") return "ТТН: помилка створення (повтор спроби…)";
    if (status === "pending_create" || status === "none") return "ТТН: створюється…";
    return "ТТН: —";
  }

  function renderOrderCard(
    order,
    {
      compact = false,
      editable = false,
      dropperActions = false,
      allowDropperEdit = false,
      editWindow = null,
      editMode = "owner",
    } = {}
  ) {
    const payload = order.payload || {};
    const recipient = payload.recipient || {};
    const delivery = payload.delivery || {};
    const cart = payload.cart || [];
    const name = [recipient.last_name, recipient.first_name, recipient.patronymic]
      .filter(Boolean)
      .join(" ");
    const itemsPreview = cart
      .slice(0, compact ? 3 : 8)
      .map((i) => `${i.code || ""} × ${i.qty || 1}`)
      .join(", ");
    const more = cart.length > (compact ? 3 : 8) ? ` +${cart.length - (compact ? 3 : 8)}` : "";
    const ttnLine = ttnStatusLabel(order);
    const hist = orderHistoryStatus(order);
    const profit = orderDropperProfit(order);
    const profitHtml =
      profit == null
        ? `<span class="order-card-profit is-empty" aria-hidden="true"></span>`
        : `<span class="order-card-profit">${escapeHtml(formatMoney(profit))}</span>`;
    const orderId = escapeHtml(String(order.id || order.order_number || ""));
    const statusSub = hist.sub
      ? `<div class="order-card-status-sub">${escapeHtml(hist.sub)}</div>`
      : "";
    const pdfHold = Boolean(payload.ttn_pdf_hold);
    const pdfHoldHtml = pdfHold
      ? `<div class="form-error order-pdf-hold">⚠️ Номер ТТН і PDF не збігаються — виправте, інакше замовлення не піде на упаковку. ${escapeHtml(
          payload.ttn_pdf_check_message || ""
        )}</div>`
      : "";
    return `
      <article class="order-card" data-order-id="${orderId}">
        <button type="button" class="order-card-toggle" aria-expanded="false">
          <div class="order-card-main">
            <div class="order-card-num">${escapeHtml(order.order_number || "")}</div>
            <div class="meta">${escapeHtml(formatOrderDate(order.created_at))}</div>
            <div class="meta">${escapeHtml(name || "—")} · ${escapeHtml(recipient.phone || "")}</div>
            <div class="meta">${escapeHtml(delivery.city || "")}</div>
            <div class="meta">Дроп ціна: <b>${escapeHtml(formatMoney(order.total || 0))}</b>
              ${order.prepay ? ` · передплата ${escapeHtml(formatMoney(order.prepay))}` : ""}
            </div>
            <div class="meta">${escapeHtml(ttnLine)}</div>
            ${pdfHoldHtml}
            <div class="meta">${escapeHtml(itemsPreview + more)}</div>
          </div>
          <div class="order-card-aside">
            <div class="order-card-status-wrap">
              <div class="order-card-status status-${escapeHtml(hist.kind)}">${escapeHtml(
                hist.label
              )}</div>
              ${statusSub}
            </div>
            <div class="order-card-aside-foot">
              ${profitHtml}
              <span class="order-card-chevron" aria-hidden="true"></span>
            </div>
          </div>
        </button>
        <div class="order-card-details hidden">
          ${renderOrderDetailsHtml(order, {
            editable,
            dropperActions,
            allowDropperEdit,
            editWindow,
            editMode,
          })}
        </div>
      </article>
    `;
  }

  function bindOrderCardClicks(root) {
    if (!root || root.dataset.orderClicksBound === "1") return;
    root.dataset.orderClicksBound = "1";
    root.addEventListener("click", (event) => {
      if (event.target.closest(
        "[data-order-edit-open], [data-order-edit-panel], .order-edit-panel, [data-order-cancel], [data-order-correction-request], [data-correction-text], [data-order-return-open], [data-order-return-form], .order-return-form, [data-order-return-submit], [data-order-return-cancel], [data-return-ttn], [data-return-error]"
      )) {
        return;
      }
      const toggle = event.target.closest(".order-card-toggle");
      if (!toggle || !root.contains(toggle)) return;
      const card = toggle.closest(".order-card");
      if (!card) return;
      const details = card.querySelector(".order-card-details");
      if (!details) return;
      const open = details.classList.toggle("hidden") === false;
      card.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  function findOrderInOwnerCaches(orderId) {
    const id = String(orderId || "");
    const boxes = document.querySelectorAll("[data-owner-orders]");
    for (const box of boxes) {
      const items = box._ordersCache || [];
      const found = items.find((o) => String(o.id) === id);
      if (found) return { order: found, box, mode: "owner" };
    }
    const dropperHit = (dropperOrdersCache || []).find((o) => String(o.id) === id);
    if (dropperHit) return { order: dropperHit, box: null, mode: "dropper" };
    return null;
  }

  function calcEditCartTotal(cart) {
    return roundMoney(
      (cart || []).reduce((sum, item) => {
        const price = Number(String(item.drop_price || "0").replace(",", ".")) || 0;
        const qty = Math.max(1, Number(item.qty) || 1);
        return sum + price * qty;
      }, 0)
    );
  }

  function renderOwnerOrderEditForm(order, options = {}) {
    const payload = order.payload || {};
    const recipient = payload.recipient || {};
    const delivery = payload.delivery || {};
    const payment = payload.payment || {};
    const cart = Array.isArray(payload.cart) ? payload.cart : [];
    const editMode = options.editMode || "owner";
    const allowCod =
      editMode === "owner" ? true : isFlagEnabled(dropperSettings.allow_cod, true);
    const allowBalance =
      editMode === "owner" ? true : Boolean(dropperSettings.allow_negative_balance);
    let method = order.payment_method || payment.method || "cod";
    if (!allowCod && method === "cod") {
      method = allowBalance ? "balance" : "requisites";
    }
    if (!allowBalance && method === "balance") {
      method = allowCod ? "cod" : "requisites";
    }
    const ownTtn = Boolean(order.own_ttn || payload.own_ttn);
    const deliveryMethod = order.delivery_method || delivery.method || "np_warehouse";
    const cartRows = cart
      .map(
        (item, index) => `
      <div class="order-edit-cart-row" data-edit-cart-index="${index}">
        <div class="meta"><b>${escapeHtml(item.code || "")}</b> · ${escapeHtml(item.name || "")}</div>
        <div class="order-edit-cart-fields">
          <label class="field compact-field">
            <span class="field-label">К-сть</span>
            <input type="number" min="1" step="1" data-edit-cart="qty" value="${escapeHtml(
              String(item.qty || 1)
            )}" />
          </label>
          <label class="field compact-field">
            <span class="field-label">Дроп ціна</span>
            <input type="number" min="0" step="1" data-edit-cart="drop_price" value="${escapeHtml(
              String(item.drop_price || 0)
            )}" ${editMode === "dropper" ? "readonly tabindex=\"-1\"" : ""} />
          </label>
          <button type="button" class="btn danger" data-edit-cart-remove="${index}">×</button>
        </div>
        <input type="hidden" data-edit-cart="code" value="${escapeHtml(item.code || "")}" />
        <input type="hidden" data-edit-cart="name" value="${escapeHtml(item.name || "")}" />
        <input type="hidden" data-edit-cart="color" value="${escapeHtml(item.color || "")}" />
        <input type="hidden" data-edit-cart="product_id" value="${escapeHtml(item.product_id || "")}" />
        <input type="hidden" data-edit-cart="drop_price_original" value="${escapeHtml(
          String(item.drop_price_original || "")
        )}" />
      </div>`
      )
      .join("");

    const paymentOptions = [
      allowCod
        ? `<option value="cod" ${method === "cod" ? "selected" : ""}>Накладний</option>`
        : "",
      `<option value="requisites" ${
        method === "requisites" ? "selected" : ""
      }>На реквізити</option>`,
      allowBalance
        ? `<option value="balance" ${method === "balance" ? "selected" : ""}>З балансу</option>`
        : "",
    ].join("");

    return `
      <form class="order-edit-form" data-order-edit-form="${escapeHtml(
        String(order.id)
      )}" data-edit-mode="${escapeHtml(editMode)}" novalidate>
        <h3 class="section-title">Редагування ${escapeHtml(order.order_number || "")}</h3>
        <div class="order-edit-grid">
          <label class="field compact-field">
            <span class="field-label">Прізвище</span>
            <input name="last_name" type="text" value="${escapeHtml(recipient.last_name || "")}" />
          </label>
          <label class="field compact-field">
            <span class="field-label">Імʼя</span>
            <input name="first_name" type="text" value="${escapeHtml(recipient.first_name || "")}" />
          </label>
          <label class="field compact-field">
            <span class="field-label">По батькові</span>
            <input name="patronymic" type="text" value="${escapeHtml(recipient.patronymic || "")}" />
          </label>
          <label class="field compact-field">
            <span class="field-label">Телефон</span>
            <input name="phone" type="tel" required value="${escapeHtml(recipient.phone || "")}" />
          </label>
          <label class="field compact-field" style="grid-column:1/-1">
            <span class="field-label">Місто</span>
            <div class="ac-field" data-edit-ac="city">
              <input
                name="city"
                type="text"
                autocomplete="off"
                placeholder="Почніть вводити назву (укр/рос)"
                value="${escapeHtml(delivery.city || "")}"
              />
              <div class="ac-dropdown hidden" data-edit-city-dropdown role="listbox"></div>
            </div>
            <p class="field-hint">Оберіть пункт зі списку Нової Пошти</p>
          </label>
          <label class="field compact-field" data-edit-warehouse-wrap style="grid-column:1/-1">
            <span class="field-label">Відділення / поштомат</span>
            <div class="ac-field" data-edit-ac="warehouse">
              <input
                name="warehouse"
                type="text"
                autocomplete="off"
                placeholder="Номер або адреса відділення"
                value="${escapeHtml(delivery.warehouse || "")}"
              />
              <div class="ac-dropdown hidden" data-edit-warehouse-dropdown role="listbox"></div>
            </div>
            <p class="field-hint">Оберіть зі списку після вибору міста</p>
          </label>
          <label class="field compact-field" data-edit-street-wrap style="grid-column:1/-1">
            <span class="field-label">Вулиця (курʼєр)</span>
            <div class="ac-field" data-edit-ac="street">
              <input
                name="street"
                type="text"
                autocomplete="off"
                placeholder="Почніть вводити назву вулиці"
                value="${escapeHtml(delivery.street || "")}"
              />
              <div class="ac-dropdown hidden" data-edit-street-dropdown role="listbox"></div>
            </div>
          </label>
          <label class="field compact-field">
            <span class="field-label">Будинок</span>
            <input name="house" type="text" value="${escapeHtml(delivery.house || "")}" />
          </label>
          <label class="field compact-field">
            <span class="field-label">Квартира</span>
            <input name="apartment" type="text" value="${escapeHtml(delivery.apartment || "")}" />
          </label>
          <label class="field compact-field">
            <span class="field-label">Доставка</span>
            <select name="delivery_method">
              <option value="np_warehouse" ${
                deliveryMethod === "np_warehouse" ? "selected" : ""
              }>НП відділення</option>
              <option value="np_courier" ${
                deliveryMethod === "np_courier" ? "selected" : ""
              }>НП курʼєр</option>
              <option value="own_ttn" ${ownTtn ? "selected" : ""}>Власна ТТН</option>
            </select>
          </label>
          <label class="field compact-field">
            <span class="field-label">Оплата</span>
            <select name="payment_method">
              ${paymentOptions}
            </select>
          </label>
          <label class="field compact-field" data-edit-prepay-wrap>
            <span class="field-label">Передплата ₴</span>
            <input name="prepay" type="number" min="0" step="1" value="${escapeHtml(
              String(order.prepay || 0)
            )}" />
          </label>
          <label class="field compact-field" data-edit-cod-wrap>
            <span class="field-label">Накладний ₴</span>
            <input name="cod_amount" type="number" min="0" step="1" value="${escapeHtml(
              String(order.cod_amount || 0)
            )}" />
          </label>
          <label class="field compact-field" data-edit-estimated-wrap>
            <span class="field-label">Оціночна вартість ₴</span>
            <input name="estimated_cost" type="number" min="1" step="1" value="${escapeHtml(
              String(
                (payload.shipment && payload.shipment.estimated_cost) ||
                  order.total ||
                  1
              )
            )}" />
          </label>
          <label class="field compact-field" data-edit-own-ttn-wrap>
            <span class="field-label">Власна ТТН / RMP</span>
            <input name="ttn_number" type="text" value="${escapeHtml(
              order.ttn_number || payload.ttn_number || ""
            )}" />
          </label>
          <label class="field compact-field" data-edit-own-ttn-wrap>
            <span class="field-label">Перевізник власної ТТН</span>
            <select name="own_ttn_carrier">
              <option value="nova_poshta" ${
                (payload.own_ttn_carrier || "nova_poshta") === "nova_poshta" ? "selected" : ""
              }>Нова Пошта</option>
              <option value="rozetka" ${
                payload.own_ttn_carrier === "rozetka" ? "selected" : ""
              }>Rozetka</option>
            </select>
          </label>
          <div class="field compact-field" data-edit-own-ttn-wrap data-edit-ttn-pdf-wrap style="grid-column:1/-1">
            <span class="field-label">Файл PDF 100×100</span>
            <label class="file-picker">
              <input
                name="ttn_pdf"
                class="file-picker-input"
                type="file"
                accept="application/pdf,.pdf"
                data-edit-ttn-pdf
              />
              <span class="file-picker-btn">Обрати файл</span>
              <span
                class="file-picker-name${payload.ttn_pdf_name ? " is-selected" : ""}"
                data-edit-ttn-pdf-name
                data-empty="Файл не обрано"
                data-current-name="${escapeHtml(payload.ttn_pdf_name || "")}"
              >${escapeHtml(payload.ttn_pdf_name || "Файл не обрано")}</span>
            </label>
            <input type="hidden" name="ttn_pdf_name" value="${escapeHtml(
              payload.ttn_pdf_name || ""
            )}" />
            <span class="field-hint">${
              payload.ttn_pdf_name
                ? "Можна замінити поточну накладну новим PDF"
                : "Обовʼязково для власної ТТН · етикетка у форматі PDF 100×100"
            }</span>
          </div>
        </div>
        <input type="hidden" name="city_ref" value="${escapeHtml(delivery.city_ref || "")}" />
        <input type="hidden" name="settlement_ref" value="${escapeHtml(
          delivery.settlement_ref || ""
        )}" />
        <input type="hidden" name="warehouse_ref" value="${escapeHtml(
          delivery.warehouse_ref || ""
        )}" />
        <input type="hidden" name="street_ref" value="${escapeHtml(delivery.street_ref || "")}" />

        <h3 class="section-title" style="margin-top:12px">Товари</h3>
        <div class="order-edit-cart" data-edit-cart-list>${cartRows || "<p class='hint'>Порожньо</p>"}</div>
        <div class="order-edit-add-row">
          <input type="text" data-edit-add-code placeholder="Код товару для додавання" />
          <button type="button" class="btn" data-edit-add-product>Додати</button>
        </div>
        <label class="field">
          <span class="field-label">Коментар</span>
          <textarea name="comment" rows="2">${escapeHtml(payload.comment || "")}</textarea>
        </label>
        <p class="form-error hidden" data-edit-error></p>
        <div class="order-edit-actions-row">
          <button type="submit" class="btn primary">Зберегти зміни</button>
          <button type="button" class="btn" data-edit-cancel>Скасувати</button>
        </div>
      </form>
    `;
  }

  function collectEditFormCart(form) {
    return [...form.querySelectorAll(".order-edit-cart-row")].map((row) => ({
      product_id: row.querySelector('[data-edit-cart="product_id"]')?.value || "",
      code: row.querySelector('[data-edit-cart="code"]')?.value || "",
      name: row.querySelector('[data-edit-cart="name"]')?.value || "",
      color: row.querySelector('[data-edit-cart="color"]')?.value || "",
      qty: Math.max(1, Number(row.querySelector('[data-edit-cart="qty"]')?.value) || 1),
      drop_price: String(row.querySelector('[data-edit-cart="drop_price"]')?.value || "0"),
      drop_price_original:
        row.querySelector('[data-edit-cart="drop_price_original"]')?.value || "",
    }));
  }

  function collectOwnerOrderEditPayload(form, order, mode = "owner") {
    const payload = order.payload || {};
    const delivery = payload.delivery || {};
    const deliveryMethod = form.delivery_method?.value || "np_warehouse";
    const ownTtn = deliveryMethod === "own_ttn";
    const cart = collectEditFormCart(form);
    const total = calcEditCartTotal(cart);
    const base =
      mode === "dropper"
        ? {
            chat_id: effectiveDropperChatId(),
            user_id: currentTelegramUser().user_id || "",
          }
        : ownerAuthBody();
    const pdfInput = form.querySelector("[data-edit-ttn-pdf]");
    const pdfFile = pdfInput?.files?.[0] || null;
    let ttnPdfName = form.ttn_pdf_name?.value?.trim() || payload.ttn_pdf_name || "";
    if (pdfFile) {
      ttnPdfName = pdfFile.name || ttnPdfName;
    }
    return {
      ...base,
      first_name: form.first_name?.value?.trim() || "",
      last_name: form.last_name?.value?.trim() || "",
      patronymic: form.patronymic?.value?.trim() || "",
      phone: form.phone?.value?.trim() || "",
      delivery_method: ownTtn ? "np_warehouse" : deliveryMethod,
      city: form.city?.value?.trim() || "",
      city_ref: form.city_ref?.value?.trim() || delivery.city_ref || "",
      settlement_ref: form.settlement_ref?.value?.trim() || delivery.settlement_ref || "",
      warehouse: form.warehouse?.value?.trim() || "",
      warehouse_ref: form.warehouse_ref?.value?.trim() || delivery.warehouse_ref || "",
      street: form.street?.value?.trim() || "",
      street_ref: form.street_ref?.value?.trim() || delivery.street_ref || "",
      house: form.house?.value?.trim() || "",
      apartment: form.apartment?.value?.trim() || "",
      own_ttn: ownTtn,
      own_ttn_carrier: form.own_ttn_carrier?.value || "nova_poshta",
      ttn_number: form.ttn_number?.value?.trim() || "",
      ttn_pdf_name: ttnPdfName,
      payment_method: form.payment_method?.value || "cod",
      prepay: Number(form.prepay?.value || 0),
      cod_amount: Number(form.cod_amount?.value || 0),
      estimated_cost: Number(form.estimated_cost?.value || 0),
      comment: form.comment?.value?.trim() || "",
      cart,
      total,
      np_city: form._editNp?.city || delivery.np_city || null,
      np_warehouse: form._editNp?.warehouse || delivery.np_warehouse || null,
      np_street: form._editNp?.street || delivery.np_street || null,
    };
  }

  function syncOrderEditDeliveryFields(form) {
    if (!form) return;
    const method = form.delivery_method?.value || "np_warehouse";
    const isCourier = method === "np_courier";
    const isOwn = method === "own_ttn";
    form.querySelectorAll("[data-edit-warehouse-wrap]").forEach((el) => {
      el.classList.toggle("hidden", isCourier || isOwn);
    });
    form.querySelectorAll("[data-edit-street-wrap]").forEach((el) => {
      el.classList.toggle("hidden", !isCourier || isOwn);
    });
    const house = form.house?.closest(".field");
    const apt = form.apartment?.closest(".field");
    if (house) house.classList.toggle("hidden", !isCourier || isOwn);
    if (apt) apt.classList.toggle("hidden", !isCourier || isOwn);
  }

  function bindOrderEditTtnPdfPicker(form) {
    if (!form) return;
    const inputEl = form.querySelector("[data-edit-ttn-pdf]");
    const nameEl = form.querySelector("[data-edit-ttn-pdf-name]");
    const hiddenName = form.querySelector('input[name="ttn_pdf_name"]');
    if (!inputEl || !nameEl || inputEl.dataset.bound === "1") return;
    inputEl.dataset.bound = "1";
    const currentName = nameEl.dataset.currentName || "";
    const emptyText = nameEl.dataset.empty || "Файл не обрано";
    const sync = () => {
      const file = inputEl.files && inputEl.files[0];
      if (file) {
        nameEl.textContent = file.name;
        nameEl.classList.add("is-selected");
        if (hiddenName) hiddenName.value = file.name;
      } else if (currentName) {
        nameEl.textContent = currentName;
        nameEl.classList.add("is-selected");
        if (hiddenName) hiddenName.value = currentName;
      } else {
        nameEl.textContent = emptyText;
        nameEl.classList.remove("is-selected");
        if (hiddenName) hiddenName.value = "";
      }
    };
    inputEl.addEventListener("change", sync);
    sync();
  }

  function bindOrderEditNpAutocomplete(form, order) {
    if (!form || form.dataset.npBound === "1") return;
    form.dataset.npBound = "1";
    const delivery = (order && order.payload && order.payload.delivery) || {};
    const state = {
      city: delivery.np_city || null,
      warehouse: delivery.np_warehouse || null,
      street: delivery.np_street || null,
      warehouseCache: { cityRef: "", query: "", items: [] },
      cityTimer: null,
      warehouseTimer: null,
      streetTimer: null,
      cityReq: 0,
      warehouseReq: 0,
      streetReq: 0,
    };
    // Відновити мінімальний стан з збережених ref, якщо немає np_* обʼєктів
    if (!state.city && (delivery.city_ref || form.city_ref?.value)) {
      state.city = {
        label: delivery.city || form.city?.value || "",
        city_ref: delivery.city_ref || form.city_ref?.value || "",
        settlement_ref: delivery.settlement_ref || form.settlement_ref?.value || "",
      };
    }
    if (!state.warehouse && (delivery.warehouse_ref || form.warehouse_ref?.value)) {
      state.warehouse = {
        label: delivery.warehouse || form.warehouse?.value || "",
        ref: delivery.warehouse_ref || form.warehouse_ref?.value || "",
      };
    }
    if (!state.street && (delivery.street_ref || form.street_ref?.value)) {
      state.street = {
        label: delivery.street || form.street?.value || "",
        ref: delivery.street_ref || form.street_ref?.value || "",
      };
    }
    form._editNp = state;

    const cityInput = form.city;
    const warehouseInput = form.warehouse;
    const streetInput = form.street;
    const cityDrop = form.querySelector("[data-edit-city-dropdown]");
    const whDrop = form.querySelector("[data-edit-warehouse-dropdown]");
    const streetDrop = form.querySelector("[data-edit-street-dropdown]");

    const mark = (input, selected) => {
      input?.closest(".ac-field")?.classList.toggle("is-selected", Boolean(selected));
    };
    const hide = (dropdown) => {
      if (!dropdown) return;
      dropdown.classList.add("hidden");
      dropdown.innerHTML = "";
    };
    const showMsg = (dropdown, text, className = "ac-empty") => {
      if (!dropdown) return;
      dropdown.innerHTML = `<div class="${className}">${escapeHtml(text)}</div>`;
      dropdown.classList.remove("hidden");
    };

    if (state.city?.city_ref) mark(cityInput, true);
    if (state.warehouse?.ref) mark(warehouseInput, true);
    if (state.street?.ref) mark(streetInput, true);

    const clearWarehouse = ({ keepText = true } = {}) => {
      state.warehouse = null;
      state.warehouseCache = { cityRef: "", query: "", items: [] };
      if (form.warehouse_ref) form.warehouse_ref.value = "";
      if (!keepText && warehouseInput) warehouseInput.value = "";
      mark(warehouseInput, false);
      hide(whDrop);
    };
    const clearStreet = ({ keepText = true } = {}) => {
      state.street = null;
      if (form.street_ref) form.street_ref.value = "";
      if (!keepText && streetInput) streetInput.value = "";
      mark(streetInput, false);
      hide(streetDrop);
    };

    const selectCityItem = (item) => {
      state.city = item;
      if (cityInput) cityInput.value = item.label || item.present || item.main_description || "";
      if (form.city_ref) form.city_ref.value = item.city_ref || "";
      if (form.settlement_ref) form.settlement_ref.value = item.settlement_ref || "";
      mark(cityInput, true);
      hide(cityDrop);
      clearWarehouse({ keepText: false });
      clearStreet({ keepText: false });
      syncEditWhEnabled();
    };
    const selectWarehouseItem = (item) => {
      state.warehouse = item;
      if (warehouseInput) warehouseInput.value = item.label || item.description || "";
      if (form.warehouse_ref) form.warehouse_ref.value = item.ref || "";
      mark(warehouseInput, true);
      hide(whDrop);
    };
    const selectStreetItem = (item) => {
      state.street = item;
      if (streetInput) streetInput.value = item.label || item.present || item.description || "";
      if (form.street_ref) form.street_ref.value = item.ref || "";
      mark(streetInput, true);
      hide(streetDrop);
    };

    const syncEditWhEnabled = () => {
      const hasCity = Boolean(state.city?.city_ref || form.city_ref?.value);
      if (warehouseInput) warehouseInput.disabled = !hasCity;
      if (streetInput) streetInput.disabled = !hasCity;
      if (!hasCity) {
        clearWarehouse({ keepText: false });
        clearStreet({ keepText: false });
      }
    };
    syncEditWhEnabled();

    async function searchEditCities(query) {
      const reqId = ++state.cityReq;
      showMsg(cityDrop, "Шукаємо...", "ac-loading");
      try {
        const response = await fetch(
          `/api/np/settlements?q=${encodeURIComponent(query)}&limit=20`
        );
        const data = await response.json();
        if (reqId !== state.cityReq) return;
        if (!response.ok) throw new Error(data.detail || "Помилка пошуку");
        const items = data.items || [];
        if (!items.length) {
          showMsg(cityDrop, "Нічого не знайдено. Спробуйте іншу назву.");
          return;
        }
        cityDrop.innerHTML = items
          .map((item, index) => {
            const title = item.label || item.present || item.main_description || "";
            const parts = [item.area, item.region].filter(Boolean).join(", ");
            return `<button type="button" class="ac-option" data-edit-city-index="${index}">
              <span>${escapeHtml(title)}</span>
              ${parts ? `<span class="ac-option-sub">${escapeHtml(parts)}</span>` : ""}
            </button>`;
          })
          .join("");
        cityDrop.dataset.items = JSON.stringify(items);
        cityDrop.classList.remove("hidden");
      } catch (error) {
        if (reqId !== state.cityReq) return;
        showMsg(cityDrop, error.message || "Помилка пошуку міст");
      }
    }

    async function searchEditWarehouses(query) {
      const cityRef = state.city?.city_ref || form.city_ref?.value;
      if (!cityRef) return;
      const q = normalizeWarehouseQuery(query);
      const limit = q ? 10 : 20;
      if (
        state.warehouseCache.cityRef === cityRef &&
        state.warehouseCache.query === q &&
        state.warehouseCache.items?.length
      ) {
        renderEditWh(state.warehouseCache.items);
        return;
      }
      const reqId = ++state.warehouseReq;
      showMsg(whDrop, "Шукаємо...", "ac-loading");
      try {
        const response = await fetch(
          `/api/np/warehouses?city_ref=${encodeURIComponent(cityRef)}&q=${encodeURIComponent(
            q
          )}&limit=${limit}`
        );
        const data = await response.json();
        if (reqId !== state.warehouseReq) return;
        if (!response.ok) throw new Error(data.detail || "Помилка пошуку");
        const items = data.items || [];
        state.warehouseCache = { cityRef, query: q, items };
        renderEditWh(items);
      } catch (error) {
        if (reqId !== state.warehouseReq) return;
        showMsg(whDrop, error.message || "Помилка пошуку відділень");
      }
    }

    function renderEditWh(items) {
      if (!items.length) {
        showMsg(whDrop, "Нічого не знайдено. Введіть номер або частину адреси.");
        return;
      }
      whDrop.innerHTML = items
        .map((item, index) => {
          const title = item.label || item.description || "";
          const sub = item.number ? `№ ${item.number}` : "";
          return `<button type="button" class="ac-option" data-edit-wh-index="${index}">
            <span>${escapeHtml(title)}</span>
            ${sub ? `<span class="ac-option-sub">${escapeHtml(sub)}</span>` : ""}
          </button>`;
        })
        .join("");
      whDrop.dataset.items = JSON.stringify(items);
      whDrop.classList.remove("hidden");
    }

    async function searchEditStreets(query) {
      const settlementRef = state.city?.settlement_ref || form.settlement_ref?.value;
      const cityRef = state.city?.city_ref || form.city_ref?.value;
      if (!settlementRef && !cityRef) return;
      const reqId = ++state.streetReq;
      showMsg(streetDrop, "Шукаємо...", "ac-loading");
      try {
        const params = new URLSearchParams({ q: query, limit: "20" });
        if (settlementRef) params.set("settlement_ref", settlementRef);
        if (cityRef) params.set("city_ref", cityRef);
        const response = await fetch(`/api/np/streets?${params.toString()}`);
        const data = await response.json();
        if (reqId !== state.streetReq) return;
        if (!response.ok) throw new Error(data.detail || "Помилка пошуку");
        const items = data.items || [];
        if (!items.length) {
          showMsg(streetDrop, "Нічого не знайдено");
          return;
        }
        streetDrop.innerHTML = items
          .map((item, index) => {
            const title = item.label || item.present || item.description || "";
            return `<button type="button" class="ac-option" data-edit-street-index="${index}">
              <span>${escapeHtml(title)}</span>
            </button>`;
          })
          .join("");
        streetDrop.dataset.items = JSON.stringify(items);
        streetDrop.classList.remove("hidden");
      } catch (error) {
        if (reqId !== state.streetReq) return;
        showMsg(streetDrop, error.message || "Помилка пошуку вулиць");
      }
    }

    cityInput?.addEventListener("input", () => {
      state.city = null;
      mark(cityInput, false);
      if (form.city_ref) form.city_ref.value = "";
      if (form.settlement_ref) form.settlement_ref.value = "";
      clearWarehouse({ keepText: false });
      clearStreet({ keepText: false });
      syncEditWhEnabled();
      clearTimeout(state.cityTimer);
      const q = cityInput.value.trim();
      if (q.length < 2) {
        hide(cityDrop);
        return;
      }
      state.cityTimer = setTimeout(() => searchEditCities(q), 300);
    });
    cityInput?.addEventListener("focus", () => {
      if (cityInput.value.trim().length >= 2 && !state.city) {
        searchEditCities(cityInput.value.trim());
      }
    });

    warehouseInput?.addEventListener("input", () => {
      state.warehouse = null;
      mark(warehouseInput, false);
      if (form.warehouse_ref) form.warehouse_ref.value = "";
      clearTimeout(state.warehouseTimer);
      const q = warehouseInput.value.trim();
      state.warehouseTimer = setTimeout(() => searchEditWarehouses(q), q ? 250 : 0);
    });
    warehouseInput?.addEventListener("focus", () => {
      if (!warehouseInput.disabled) searchEditWarehouses(warehouseInput.value.trim());
    });

    streetInput?.addEventListener("input", () => {
      state.street = null;
      mark(streetInput, false);
      if (form.street_ref) form.street_ref.value = "";
      clearTimeout(state.streetTimer);
      const q = streetInput.value.trim();
      if (q.length < 2) {
        hide(streetDrop);
        return;
      }
      state.streetTimer = setTimeout(() => searchEditStreets(q), 300);
    });
    streetInput?.addEventListener("focus", () => {
      if (!streetInput.disabled && streetInput.value.trim().length >= 2 && !state.street) {
        searchEditStreets(streetInput.value.trim());
      }
    });

    cityDrop?.addEventListener("mousedown", (event) => {
      const btn = event.target.closest("[data-edit-city-index]");
      if (!btn) return;
      event.preventDefault();
      try {
        const items = JSON.parse(cityDrop.dataset.items || "[]");
        const item = items[Number(btn.getAttribute("data-edit-city-index"))];
        if (item) selectCityItem(item);
      } catch {
        /* ignore */
      }
    });
    whDrop?.addEventListener("mousedown", (event) => {
      const btn = event.target.closest("[data-edit-wh-index]");
      if (!btn) return;
      event.preventDefault();
      try {
        const items = JSON.parse(whDrop.dataset.items || "[]");
        const item = items[Number(btn.getAttribute("data-edit-wh-index"))];
        if (item) selectWarehouseItem(item);
      } catch {
        /* ignore */
      }
    });
    streetDrop?.addEventListener("mousedown", (event) => {
      const btn = event.target.closest("[data-edit-street-index]");
      if (!btn) return;
      event.preventDefault();
      try {
        const items = JSON.parse(streetDrop.dataset.items || "[]");
        const item = items[Number(btn.getAttribute("data-edit-street-index"))];
        if (item) selectStreetItem(item);
      } catch {
        /* ignore */
      }
    });

    form.delivery_method?.addEventListener("change", () => syncOrderEditDeliveryFields(form));
    syncOrderEditDeliveryFields(form);
  }

  function syncOrderEditPaymentFields(form) {
    if (!form) return;
    const method = form.payment_method?.value || "cod";
    const isCod = method === "cod";
    form.querySelectorAll("[data-edit-prepay-wrap]").forEach((el) => {
      el.classList.toggle("hidden", !isCod);
    });
    form.querySelectorAll("[data-edit-cod-wrap]").forEach((el) => {
      el.classList.toggle("hidden", !isCod);
    });
    form.querySelectorAll("[data-edit-estimated-wrap]").forEach((el) => {
      el.classList.toggle("hidden", isCod);
    });
  }

  async function openOwnerOrderEdit(orderId, card, modeHint) {
    const hit = findOrderInOwnerCaches(orderId);
    if (!hit) {
      showToast("Замовлення не знайдено в кеші");
      return;
    }
    const mode = modeHint || hit.mode || "owner";
    const panel = card.querySelector(`[data-order-edit-panel="${orderId}"]`);
    if (!panel) return;
    panel.innerHTML = renderOwnerOrderEditForm(hit.order, { editMode: mode });
    panel.classList.remove("hidden");
    panel._orderRef = hit.order;
    panel._boxRef = hit.box;
    panel._editMode = mode;
    const form = panel.querySelector("[data-order-edit-form]");
    syncOrderEditPaymentFields(form);
    form?.payment_method?.addEventListener("change", () => syncOrderEditPaymentFields(form));
    bindOrderEditNpAutocomplete(form, hit.order);
    bindOrderEditTtnPdfPicker(form);
  }

  async function saveOwnerOrderEdit(form) {
    const orderId = form.getAttribute("data-order-edit-form");
    const panel = form.closest("[data-order-edit-panel]");
    const order = panel?._orderRef;
    const mode = panel?._editMode || "owner";
    const errEl = form.querySelector("[data-edit-error]");
    if (errEl) {
      errEl.classList.add("hidden");
      errEl.textContent = "";
    }
    if (!order) return;
    const body = collectOwnerOrderEditPayload(form, order, mode);
    if (!body.cart.length) {
      if (errEl) {
        errEl.textContent = "Додайте хоча б один товар";
        errEl.classList.remove("hidden");
      }
      return;
    }
    if (body.own_ttn) {
      const pdfInput = form.querySelector("[data-edit-ttn-pdf]");
      const pdfFile = pdfInput?.files?.[0] || null;
      const pdfName = String(body.ttn_pdf_name || "").trim();
      if (!pdfName) {
        if (errEl) {
          errEl.textContent = "Прикріпіть файл PDF 100×100";
          errEl.classList.remove("hidden");
        }
        return;
      }
      if (pdfFile) {
        const lower = (pdfFile.name || "").toLowerCase();
        const type = pdfFile.type || "";
        if (!lower.endsWith(".pdf") && type !== "application/pdf") {
          if (errEl) {
            errEl.textContent = "Файл 100×100 має бути у форматі PDF";
            errEl.classList.remove("hidden");
          }
          return;
        }
        try {
          body.ttn_pdf_base64 = await readFileAsBase64(pdfFile);
        } catch (e) {
          if (errEl) {
            errEl.textContent = e.message || "Не вдалося прочитати PDF";
            errEl.classList.remove("hidden");
          }
          return;
        }
      } else {
        if (!pdfName.toLowerCase().endsWith(".pdf")) {
          if (errEl) {
            errEl.textContent = "Файл 100×100 має бути у форматі PDF";
            errEl.classList.remove("hidden");
          }
          return;
        }
        const oldTtn = String(order.ttn_number || "")
          .replace(/\s+/g, "")
          .toUpperCase();
        const newTtn = String(body.ttn_number || "")
          .replace(/\s+/g, "")
          .toUpperCase();
        if (oldTtn !== newTtn) {
          if (errEl) {
            errEl.textContent =
              "При зміні номера накладної прикріпіть PDF етикетки ще раз — для звірки номера";
            errEl.classList.remove("hidden");
          }
          return;
        }
      }
    }
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;
    try {
      const url =
        mode === "dropper"
          ? `/api/dropper/orders/${encodeURIComponent(orderId)}`
          : `/api/owner/orders/${encodeURIComponent(orderId)}`;
      const response = await fetch(url, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Помилка збереження");
      }
      const updated = data.order;
      const box = panel._boxRef;
      if (box && Array.isArray(box._ordersCache) && updated) {
        box._ordersCache = box._ordersCache.map((o) =>
          String(o.id) === String(updated.id) ? updated : o
        );
        renderOwnerDropperOrdersPanel(box);
      } else if (mode === "dropper") {
        await renderOrdersHistory();
      }
      let msg = "Замовлення збережено";
      if (data.ttn_recreated) msg += ` · нова ТТН ${updated?.ttn_number || ""}`;
      if (data.ttn_error) msg += ` · ТТН: ${data.ttn_error}`;
      showToast(msg);
    } catch (error) {
      if (errEl) {
        errEl.textContent = error.message || "Помилка";
        errEl.classList.remove("hidden");
      } else {
        showToast(error.message || "Помилка");
      }
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  async function addProductToEditForm(form) {
    const input = form.querySelector("[data-edit-add-code]");
    const code = input?.value?.trim() || "";
    if (!code) return;
    const list = form.querySelector("[data-edit-cart-list]");
    if (!list) return;
    try {
      const params = new URLSearchParams({ q: code, limit: "5" });
      const response = await fetch(`/api/products/search?${params.toString()}`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Пошук не вдався");
      }
      const item = (data.items || data.results || [])[0];
      if (!item) {
        showToast("Товар не знайдено");
        return;
      }
      const cart = collectEditFormCart(form);
      cart.push({
        product_id: item.product_id || "",
        code: item.code || code,
        name: item.name || "",
        color: item.color || "",
        qty: 1,
        drop_price: String(item.drop_price || item.price || 0),
        drop_price_original: item.drop_price_original || "",
      });
      // re-render cart only via temporary order stub
      const stub = {
        id: form.getAttribute("data-order-edit-form"),
        order_number: "",
        payload: {
          ...(form.closest("[data-order-edit-panel]")?._orderRef?.payload || {}),
          cart,
        },
        payment_method: form.payment_method?.value,
        own_ttn: form.delivery_method?.value === "own_ttn",
        prepay: form.prepay?.value,
        cod_amount: form.cod_amount?.value,
        ttn_number: form.ttn_number?.value,
      };
      // preserve filled fields: rebuild form
      const panel = form.closest("[data-order-edit-panel]");
      const preserved = collectOwnerOrderEditPayload(
        form,
        panel._orderRef || stub,
        panel._editMode || "owner"
      );
      panel._orderRef = {
        ...panel._orderRef,
        payload: {
          ...(panel._orderRef.payload || {}),
          recipient: {
            first_name: preserved.first_name,
            last_name: preserved.last_name,
            patronymic: preserved.patronymic,
            phone: preserved.phone,
          },
          delivery: {
            ...(panel._orderRef.payload?.delivery || {}),
            city: preserved.city,
            warehouse: preserved.warehouse,
            street: preserved.street,
            house: preserved.house,
            apartment: preserved.apartment,
            method: preserved.own_ttn ? "own_ttn" : preserved.delivery_method,
          },
          comment: preserved.comment,
          cart,
          own_ttn_carrier: preserved.own_ttn_carrier,
          ttn_number: preserved.ttn_number,
          ttn_pdf_name: preserved.ttn_pdf_name,
        },
        payment_method: preserved.payment_method,
        own_ttn: preserved.own_ttn,
        prepay: preserved.prepay,
        cod_amount: preserved.cod_amount,
        ttn_number: preserved.ttn_number,
        delivery_method: preserved.own_ttn ? "own_ttn" : preserved.delivery_method,
      };
      panel.innerHTML = renderOwnerOrderEditForm(panel._orderRef, {
        editMode: panel._editMode || "owner",
      });
      if (input) input.value = "";
      const formAfter = panel.querySelector("[data-order-edit-form]");
      syncOrderEditPaymentFields(formAfter);
      formAfter?.payment_method?.addEventListener("change", () =>
        syncOrderEditPaymentFields(formAfter)
      );
      bindOrderEditNpAutocomplete(formAfter, panel._orderRef);
      bindOrderEditTtnPdfPicker(formAfter);
    } catch (error) {
      showToast(error.message || "Помилка пошуку");
    }
  }

  document.addEventListener("click", (event) => {
    const openBtn = event.target.closest("[data-order-edit-open]");
    if (openBtn) {
      event.preventDefault();
      const orderId = openBtn.getAttribute("data-order-edit-open");
      const mode = openBtn.getAttribute("data-order-edit-mode") || "owner";
      const card = openBtn.closest(".order-card");
      if (orderId && card) openOwnerOrderEdit(orderId, card, mode);
      return;
    }
    const cancelOrderBtn = event.target.closest("[data-order-cancel]");
    if (cancelOrderBtn) {
      event.preventDefault();
      const orderId = cancelOrderBtn.getAttribute("data-order-cancel");
      if (orderId) cancelDropperOrder(orderId);
      return;
    }
    const correctionBtn = event.target.closest("[data-order-correction-request]");
    if (correctionBtn) {
      event.preventDefault();
      const orderId = correctionBtn.getAttribute("data-order-correction-request");
      const wrap = correctionBtn.closest(".order-edit-actions");
      const text = wrap?.querySelector("[data-correction-text]")?.value?.trim() || "";
      if (orderId) requestOrderCorrection(orderId, text);
      return;
    }
    const returnOpenBtn = event.target.closest("[data-order-return-open]");
    if (returnOpenBtn) {
      event.preventDefault();
      const orderId = returnOpenBtn.getAttribute("data-order-return-open");
      const form = document.querySelector(`[data-order-return-form="${orderId}"]`);
      if (form) form.classList.toggle("hidden");
      return;
    }
    const returnCancelBtn = event.target.closest("[data-order-return-cancel]");
    if (returnCancelBtn) {
      event.preventDefault();
      const orderId = returnCancelBtn.getAttribute("data-order-return-cancel");
      const form = document.querySelector(`[data-order-return-form="${orderId}"]`);
      if (form) {
        form.classList.add("hidden");
        const err = form.querySelector("[data-return-error]");
        if (err) {
          err.classList.add("hidden");
          err.textContent = "";
        }
      }
      return;
    }
    const returnSubmitBtn = event.target.closest("[data-order-return-submit]");
    if (returnSubmitBtn) {
      event.preventDefault();
      const orderId = returnSubmitBtn.getAttribute("data-order-return-submit");
      if (orderId) submitDropperReturn(orderId);
      return;
    }
    const cancelBtn = event.target.closest("[data-edit-cancel]");
    if (cancelBtn) {
      const panel = cancelBtn.closest("[data-order-edit-panel]");
      if (panel) {
        panel.classList.add("hidden");
        panel.innerHTML = "";
      }
      return;
    }
    const removeBtn = event.target.closest("[data-edit-cart-remove]");
    if (removeBtn) {
      const row = removeBtn.closest(".order-edit-cart-row");
      if (row) row.remove();
      return;
    }
    const addBtn = event.target.closest("[data-edit-add-product]");
    if (addBtn) {
      const form = addBtn.closest("[data-order-edit-form]");
      if (form) addProductToEditForm(form);
    }
  });

  async function cancelDropperOrder(orderId) {
    if (!window.confirm("Скасувати замовлення? ТТН буде видалено, наявність повернеться.")) {
      return;
    }
    try {
      const response = await fetch(`/api/dropper/orders/${encodeURIComponent(orderId)}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: effectiveDropperChatId(),
          user_id: currentTelegramUser().user_id || "",
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Помилка скасування");
      }
      showToast("Замовлення скасовано");
      await renderOrdersHistory();
    } catch (error) {
      showToast(error.message || "Помилка");
    }
  }

  async function requestOrderCorrection(orderId, message) {
    try {
      const response = await fetch(
        `/api/dropper/orders/${encodeURIComponent(orderId)}/correction-request`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: effectiveDropperChatId(),
            user_id: currentTelegramUser().user_id || "",
            message: message || "",
          }),
        }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Помилка запиту");
      }
      showToast("Запит надіслано власнику");
      await renderOrdersHistory();
    } catch (error) {
      showToast(error.message || "Помилка");
    }
  }

  async function submitDropperReturn(orderId) {
    const form = document.querySelector(`[data-order-return-form="${orderId}"]`);
    const errEl = form?.querySelector("[data-return-error]");
    const rawTtn = form?.querySelector("[data-return-ttn]")?.value?.trim() || "";
    const type =
      form?.querySelector(`input[name="returnType-${orderId}"]:checked`)?.value ||
      "regular";
    if (errEl) {
      errEl.classList.add("hidden");
      errEl.textContent = "";
    }
    const checked = validateReturnTtn(rawTtn);
    if (!checked.ok) {
      if (errEl) {
        errEl.textContent = checked.message;
        errEl.classList.remove("hidden");
      } else {
        showToast(checked.message);
      }
      return;
    }
    const submitBtn = form?.querySelector("[data-order-return-submit]");
    if (submitBtn) submitBtn.disabled = true;
    try {
      const response = await fetch(
        `/api/dropper/orders/${encodeURIComponent(orderId)}/return`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: effectiveDropperChatId(),
            user_id: currentTelegramUser().user_id || "",
            ttn_number: checked.ttn,
            return_type: type,
          }),
        }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
      }
      showToast("Заявку надіслано · очікує отримання");
      historyBucket = "returns";
      syncHistoryBucketTabs();
      await renderOrdersHistory();
    } catch (error) {
      if (errEl) {
        errEl.textContent = error.message || "Помилка";
        errEl.classList.remove("hidden");
      } else {
        showToast(error.message || "Помилка");
      }
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("[data-order-edit-form]");
    if (!form) return;
    event.preventDefault();
    saveOwnerOrderEdit(form);
  });

  let dropperOrdersEditWindow = null;
  let dropperOrdersCache = [];
  let historyBucket = "awaiting";
  const ORDERS_PAGE_SIZE = 20;
  let historyPage = 0;

  function syncHistoryBucketTabs() {
    if (!els.historyBuckets) return;
    els.historyBuckets.querySelectorAll("[data-history-bucket]").forEach((btn) => {
      btn.classList.toggle(
        "active",
        btn.getAttribute("data-history-bucket") === historyBucket
      );
    });
  }

  function paintOrdersHistoryList() {
    if (!els.ordersHistory) return;
    const items = dropperOrdersCache || [];
    const inBucket = items.filter((o) => orderHistoryBucket(o) === historyBucket);
    const filters = collectOrderFilterValues(els.historyFiltersPanel);
    const filtered = inBucket.filter((o) => orderMatchesOwnerFilters(o, filters));
    const pageCount = Math.max(1, Math.ceil(filtered.length / ORDERS_PAGE_SIZE) || 1);
    if (historyPage >= pageCount) historyPage = Math.max(0, pageCount - 1);
    if (historyPage < 0) historyPage = 0;
    const start = historyPage * ORDERS_PAGE_SIZE;
    const pageItems = filtered.slice(start, start + ORDERS_PAGE_SIZE);
    const lockedHint =
      historyBucket === "awaiting" && dropperOrdersEditWindow?.locked
        ? `<div class="hint order-window-banner">${escapeHtml(
            dropperOrdersEditWindow.message ||
              "11:50–14:30 — редагування закрите, можна лише запит власнику."
          )}</div>`
        : historyBucket === "awaiting" && dropperOrdersEditWindow
          ? `<div class="hint order-window-banner">${escapeHtml(
              dropperOrdersEditWindow.message || ""
            )}</div>`
          : "";
    const emptyByBucket = {
      awaiting: "Немає замовлень, що очікують відправлення",
      transit: "Немає замовлень у дорозі",
      received: "Немає отриманих замовлень",
      returns: "Немає повернень",
    };
    if (els.historyOrdersCount) {
      if (!inBucket.length) {
        els.historyOrdersCount.classList.add("hidden");
        els.historyOrdersCount.textContent = "";
      } else {
        els.historyOrdersCount.classList.remove("hidden");
        const shown = pageItems.length;
        els.historyOrdersCount.textContent = `Показано ${shown} з ${filtered.length} (у вкладці ${inBucket.length})`;
      }
    }
    if (els.historyPageLabel) {
      els.historyPageLabel.textContent =
        filtered.length > 0
          ? `${historyPage + 1} / ${pageCount}`
          : "0 / 0";
    }
    if (els.historyPagePrev) els.historyPagePrev.disabled = historyPage <= 0;
    if (els.historyPageNext) {
      els.historyPageNext.disabled =
        filtered.length === 0 || historyPage >= pageCount - 1;
    }
    els.ordersHistory.innerHTML =
      lockedHint +
      (pageItems.length
        ? pageItems
            .map((o) =>
              renderOrderCard(o, {
                dropperActions: true,
                allowDropperEdit: historyBucket === "awaiting",
                editWindow: dropperOrdersEditWindow,
                editMode: "dropper",
              })
            )
            .join("")
        : `<div class="empty">${escapeHtml(
            inBucket.length
              ? "Нічого не знайдено за фільтрами"
              : emptyByBucket[historyBucket] || "Порожньо"
          )}</div>`);
    bindOrderCardClicks(els.ordersHistory);
  }

  async function renderOrdersHistory() {
    if (!els.ordersHistory) return;
    const chatId = effectiveDropperChatId();
    syncHistoryBucketTabs();
    historyPage = 0;
    els.ordersHistory.innerHTML = `<div class="ac-loading">Завантаження історії...</div>`;
    try {
      const response = await fetch(
        `/api/dropper/orders?chat_id=${encodeURIComponent(chatId)}&limit=500`
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
      }
      dropperOrdersCache = data.items || [];
      dropperOrdersEditWindow = data.edit_window || null;
      paintOrdersHistoryList();
    } catch (error) {
      els.ordersHistory.innerHTML = `<div class="form-error">${escapeHtml(
        error.message || "Помилка"
      )}</div>`;
    }
  }

  async function loadOwnerDropperOrders(card) {
    const chatId =
      card.getAttribute("data-balance-chat") || card.getAttribute("data-dropper-chat");
    if (!chatId) return;

    let box = card.querySelector("[data-owner-orders]");
    if (!box) {
      box = document.createElement("div");
      box.className = "owner-orders";
      box.setAttribute("data-owner-orders", "1");
      card.appendChild(box);
    }

    if (!box.dataset.loaded) {
      box.innerHTML = `<div class="ac-loading">Завантаження замовлень...</div>`;
      try {
        const response = await fetch(
          `/api/owner/droppers/${encodeURIComponent(chatId)}/orders?${ownerAuthParams()}&limit=500`
        );
        const data = await response.json();
        if (!response.ok) {
          throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
        }
        box._ordersCache = data.items || [];
        box._ordersPage = 0;
        box.dataset.dropperChat = chatId;
        box.dataset.loaded = "1";
      } catch (error) {
        box.innerHTML = `<div class="form-error">${escapeHtml(error.message || "Помилка")}</div>`;
        return;
      }
    }

    renderOwnerDropperOrdersPanel(box);
  }

  function collectOrderFilterValues(root) {
    if (!root) {
      return {
        productCode: "",
        orderNumber: "",
        phone: "",
        clientName: "",
        ttnNumber: "",
        dateFrom: "",
        dateTo: "",
      };
    }
    return {
      productCode: root.querySelector("[data-filter-code]")?.value?.trim() || "",
      orderNumber: root.querySelector("[data-filter-order]")?.value?.trim() || "",
      phone: root.querySelector("[data-filter-phone]")?.value?.trim() || "",
      clientName: root.querySelector("[data-filter-name]")?.value?.trim() || "",
      ttnNumber: root.querySelector("[data-filter-ttn]")?.value?.trim() || "",
      dateFrom: root.querySelector("[data-filter-date-from]")?.value || "",
      dateTo: root.querySelector("[data-filter-date-to]")?.value || "",
    };
  }

  function ownerOrderFilterValues(box) {
    const base = collectOrderFilterValues(box);
    base.status = box?._ordersBucket || "transit";
    return base;
  }

  function orderCreatedDateLocal(order) {
    const raw = String(order.created_at || "").trim();
    if (!raw) return null;
    const dt = new Date(raw);
    if (!Number.isFinite(dt.getTime())) return null;
    const y = dt.getFullYear();
    const m = String(dt.getMonth() + 1).padStart(2, "0");
    const d = String(dt.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }

  function orderMatchesOwnerFilters(order, filters) {
    const payload = order.payload || {};
    const recipient = payload.recipient || {};
    const cart = payload.cart || [];

    if (filters.productCode) {
      const q = filters.productCode.toLowerCase();
      const hit = cart.some((item) => String(item.code || "").toLowerCase().includes(q));
      if (!hit) return false;
    }

    if (filters.orderNumber) {
      const q = filters.orderNumber.toLowerCase();
      if (!String(order.order_number || "").toLowerCase().includes(q)) return false;
    }

    if (filters.ttnNumber) {
      const q = String(filters.ttnNumber).replace(/\s+/g, "").toLowerCase();
      const ttn = String(order.ttn_number || payload.ttn_number || "")
        .replace(/\s+/g, "")
        .toLowerCase();
      if (!q || !ttn.includes(q)) return false;
    }

    if (filters.phone) {
      const q = String(filters.phone).replace(/\D/g, "");
      const phone = String(recipient.phone || "").replace(/\D/g, "");
      if (!q || !phone.includes(q)) return false;
    }

    if (filters.clientName) {
      const tokens = filters.clientName
        .toLowerCase()
        .split(/\s+/)
        .map((t) => t.trim())
        .filter(Boolean);
      const last = String(recipient.last_name || "").toLowerCase();
      const first = String(recipient.first_name || "").toLowerCase();
      const full = `${last} ${first}`.trim();
      const fullRev = `${first} ${last}`.trim();
      if (!tokens.length) return true;
      if (tokens.length === 1) {
        const t = tokens[0];
        if (!(last.includes(t) || first.includes(t) || full.includes(t))) return false;
      } else {
        const joined = tokens.join(" ");
        const [a, b] = tokens;
        const pairOk =
          full.includes(joined) ||
          fullRev.includes(joined) ||
          (last.includes(a) && first.includes(b)) ||
          (last.includes(b) && first.includes(a));
        if (!pairOk) return false;
      }
    }

    if (filters.dateFrom || filters.dateTo) {
      const day = orderCreatedDateLocal(order);
      if (!day) return false;
      if (filters.dateFrom && day < filters.dateFrom) return false;
      if (filters.dateTo && day > filters.dateTo) return false;
    }

    return true;
  }

  function syncOwnerOrdersBucketTabs(box) {
    const bucket = box._ordersBucket || "transit";
    box.querySelectorAll("[data-owner-orders-bucket]").forEach((btn) => {
      btn.classList.toggle(
        "active",
        btn.getAttribute("data-owner-orders-bucket") === bucket
      );
    });
  }

  function ensureOwnerOrdersAwaitingTab(box) {
    const nav = box.querySelector("[data-owner-orders-buckets]");
    if (!nav || nav.querySelector('[data-owner-orders-bucket="awaiting"]')) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tab";
    btn.setAttribute("data-owner-orders-bucket", "awaiting");
    btn.textContent = "Очікує відправлення";
    nav.insertBefore(btn, nav.firstChild);
  }

  function renderOwnerDropperOrdersPanel(box) {
    if (box._ordersPage == null) box._ordersPage = 0;
    if (!box._ordersBucket) box._ordersBucket = "transit";

    if (!box.querySelector("[data-owner-order-filters]")) {
      box.innerHTML = `
        <p class="owner-orders-title">Історія замовлень</p>
        <nav class="tabs history-buckets owner-orders-buckets" data-owner-orders-buckets aria-label="Статус замовлень">
          <button type="button" class="tab" data-owner-orders-bucket="awaiting">Очікує відправлення</button>
          <button type="button" class="tab active" data-owner-orders-bucket="transit">В дорозі</button>
          <button type="button" class="tab" data-owner-orders-bucket="received">Отримано</button>
          <button type="button" class="tab" data-owner-orders-bucket="returns">Повернення</button>
        </nav>
        <div class="orders-toolbar">
          <button type="button" class="btn secondary" data-owner-filters-toggle>Фільтри</button>
          <button type="button" class="btn secondary" data-owner-orders-excel>Excel</button>
          <div class="orders-pager">
            <button type="button" class="btn secondary orders-pager-btn" data-owner-page-prev aria-label="Попередні">‹</button>
            <span class="orders-pager-label" data-owner-page-label></span>
            <button type="button" class="btn secondary orders-pager-btn" data-owner-page-next aria-label="Наступні">›</button>
          </div>
        </div>
        <div class="owner-orders-filters hidden" data-owner-order-filters>
          <label class="field compact-field">
            <span class="field-label">Код товару</span>
            <input type="text" data-filter-code placeholder="Напр. 1469Д" autocomplete="off" />
          </label>
          <label class="field compact-field">
            <span class="field-label">№ замовлення</span>
            <input type="text" data-filter-order placeholder="К-…" autocomplete="off" />
          </label>
          <label class="field compact-field">
            <span class="field-label">Номер накладної</span>
            <input type="text" data-filter-ttn placeholder="ТТН / RMP…" autocomplete="off" />
          </label>
          <label class="field compact-field">
            <span class="field-label">Телефон клієнта</span>
            <input type="text" data-filter-phone placeholder="+380…" autocomplete="off" />
          </label>
          <label class="field compact-field">
            <span class="field-label">Прізвище / імʼя</span>
            <input type="text" data-filter-name placeholder="Прізвище або Імʼя" autocomplete="off" />
          </label>
          <label class="field compact-field">
            <span class="field-label">Дата від</span>
            <input type="date" data-filter-date-from />
          </label>
          <label class="field compact-field">
            <span class="field-label">Дата до</span>
            <input type="date" data-filter-date-to />
          </label>
          <div class="owner-orders-filters-actions">
            <button type="button" class="btn secondary" data-filter-reset>Скинути фільтри</button>
          </div>
        </div>
        <p class="meta-soft" data-orders-count></p>
        <div data-owner-orders-list></div>
      `;
      if (!box.dataset.filtersBound) {
        box.dataset.filtersBound = "1";
        box.addEventListener("input", (event) => {
          if (!event.target.closest("[data-owner-order-filters]")) return;
          box._ordersPage = 0;
          renderOwnerDropperOrdersList(box);
        });
        box.addEventListener("change", (event) => {
          if (!event.target.closest("[data-owner-order-filters]")) return;
          box._ordersPage = 0;
          renderOwnerDropperOrdersList(box);
        });
        box.addEventListener("click", async (event) => {
          const bucketBtn = event.target.closest("[data-owner-orders-bucket]");
          if (bucketBtn && box.contains(bucketBtn)) {
            const bucket = bucketBtn.getAttribute("data-owner-orders-bucket");
            if (!bucket || bucket === box._ordersBucket) return;
            box._ordersBucket = bucket;
            box._ordersPage = 0;
            syncOwnerOrdersBucketTabs(box);
            renderOwnerDropperOrdersList(box);
            return;
          }
          const toggle = event.target.closest("[data-owner-filters-toggle]");
          if (toggle && box.contains(toggle)) {
            const panel = box.querySelector("[data-owner-order-filters]");
            if (!panel) return;
            const open = panel.classList.toggle("hidden") === false;
            toggle.classList.toggle("active", open);
            toggle.textContent = open ? "Сховати фільтри" : "Фільтри";
            return;
          }
          const reset = event.target.closest("[data-filter-reset]");
          if (reset && box.contains(reset)) {
            box.querySelectorAll("[data-owner-order-filters] input").forEach((input) => {
              input.value = "";
            });
            box._ordersPage = 0;
            renderOwnerDropperOrdersList(box);
            return;
          }
          const excelBtn = event.target.closest("[data-owner-orders-excel]");
          if (excelBtn && box.contains(excelBtn)) {
            await downloadOwnerDropperOrdersExcel(box);
            return;
          }
          const prev = event.target.closest("[data-owner-page-prev]");
          if (prev && box.contains(prev)) {
            box._ordersPage = Math.max(0, (box._ordersPage || 0) - 1);
            renderOwnerDropperOrdersList(box);
            return;
          }
          const next = event.target.closest("[data-owner-page-next]");
          if (next && box.contains(next)) {
            box._ordersPage = (box._ordersPage || 0) + 1;
            renderOwnerDropperOrdersList(box);
          }
        });
      }
    }

    ensureOwnerOrdersAwaitingTab(box);
    syncOwnerOrdersBucketTabs(box);
    renderOwnerDropperOrdersList(box);
  }

  function renderOwnerDropperOrdersList(box) {
    const all = Array.isArray(box._ordersCache) ? box._ordersCache : [];
    const bucket = box._ordersBucket || "transit";
    const filters = ownerOrderFilterValues(box);
    const inBucket = all.filter((o) => orderHistoryBucket(o) === bucket);
    const filtered = inBucket.filter((o) => orderMatchesOwnerFilters(o, filters));
    const page = Math.max(0, Number(box._ordersPage) || 0);
    const pageCount = Math.max(1, Math.ceil(filtered.length / ORDERS_PAGE_SIZE) || 1);
    const safePage = Math.min(page, pageCount - 1);
    box._ordersPage = safePage;
    const start = safePage * ORDERS_PAGE_SIZE;
    const pageItems = filtered.slice(start, start + ORDERS_PAGE_SIZE);
    const countEl = box.querySelector("[data-orders-count]");
    const listEl = box.querySelector("[data-owner-orders-list]");
    const pageLabel = box.querySelector("[data-owner-page-label]");
    const prevBtn = box.querySelector("[data-owner-page-prev]");
    const nextBtn = box.querySelector("[data-owner-page-next]");
    const emptyByBucket = {
      awaiting: "Немає замовлень, що очікують відправлення",
      transit: "Немає замовлень у дорозі",
      received: "Немає отриманих замовлень",
      returns: "Немає повернень",
    };
    if (countEl) {
      countEl.textContent = inBucket.length
        ? `Показано ${pageItems.length} з ${filtered.length}`
        : "Показано 0 з 0";
    }
    if (pageLabel) {
      pageLabel.textContent = filtered.length ? `${safePage + 1} / ${pageCount}` : "0 / 0";
    }
    if (prevBtn) prevBtn.disabled = safePage <= 0;
    if (nextBtn) nextBtn.disabled = filtered.length === 0 || safePage >= pageCount - 1;
    if (listEl) {
      listEl.innerHTML = pageItems.length
        ? pageItems
            .map((o) =>
              renderOrderCard(o, { compact: true, editable: true, editMode: "owner" })
            )
            .join("")
        : `<div class="empty">${
            inBucket.length
              ? "Нічого не знайдено за фільтрами"
              : emptyByBucket[bucket] || "Замовлень ще немає"
          }</div>`;
      bindOrderCardClicks(listEl);
    }
  }

  async function downloadBlobUrl(url, fallbackName) {
    const response = await fetch(url);
    if (!response.ok) {
      let detail = "Помилка вивантаження";
      try {
        const data = await response.json();
        if (typeof data.detail === "string") detail = data.detail;
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    const blob = await response.blob();
    const disp = response.headers.get("Content-Disposition") || "";
    const match = /filename=\"([^\"]+)\"/i.exec(disp);
    const name = match ? match[1] : fallbackName;
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(objectUrl);
  }

  async function downloadOwnerDropperOrdersExcel(box) {
    const chatId =
      box.dataset.dropperChat ||
      box.closest("[data-balance-chat]")?.getAttribute("data-balance-chat") ||
      box.closest("[data-dropper-chat]")?.getAttribute("data-dropper-chat") ||
      "";
    if (!chatId) {
      showToast("Немає chat_id дроппера");
      return;
    }
    const filters = ownerOrderFilterValues(box);
    const params = new URLSearchParams(ownerAuthParams());
    if (filters.status && filters.status !== "all") params.set("status", filters.status);
    if (filters.dateFrom) params.set("date_from", filters.dateFrom);
    if (filters.dateTo) params.set("date_to", filters.dateTo);
    try {
      await downloadBlobUrl(
        `/api/owner/droppers/${encodeURIComponent(chatId)}/orders/export.xlsx?${params}`,
        "orders.xlsx"
      );
      showToast("Excel завантажено");
    } catch (error) {
      showToast(error.message || "Помилка Excel");
    }
  }

  els.searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = els.searchInput.value.trim();
    const color = (colorState.selected || els.colorFilter?.value || "").trim();
    if (!query && !color) {
      els.status.textContent = "Введіть код/назву або оберіть колір у фільтрах";
      return;
    }

    els.status.textContent = "Шукаємо...";
    els.results.innerHTML = "";

    try {
      const params = new URLSearchParams();
      if (query) params.set("q", query);
      if (color) params.set("color", color);
      const chatId = effectiveDropperChatId();
      if (chatId) params.set("chat_id", chatId);
      const response = await fetch(`/api/products/search?${params.toString()}`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Помилка пошуку");
      }
      renderResults(data.items || []);
    } catch (error) {
      els.status.textContent = error.message || "Помилка пошуку";
    }
  });

  if (els.filtersToggle && els.filtersPanel) {
    els.filtersToggle.addEventListener("click", () => {
      const open = els.filtersPanel.classList.toggle("hidden") === false;
      els.filtersToggle.setAttribute("aria-expanded", open ? "true" : "false");
      els.filtersToggle.classList.toggle("is-open", open);
      if (open && els.colorFilter && !els.colorFilter.value.trim()) {
        scheduleColorSearch("");
      }
    });
  }

  if (els.filtersClear) {
    els.filtersClear.addEventListener("click", () => {
      setColorFilter("", { runSearch: Boolean(els.searchInput.value.trim()) });
      if (!els.searchInput.value.trim()) {
        els.results.innerHTML = "";
        els.status.textContent = "";
      }
    });
  }

  if (els.colorFilter) {
    els.colorFilter.addEventListener("input", () => {
      colorState.selected = "";
      syncFiltersUi();
      scheduleColorSearch(els.colorFilter.value);
    });
    els.colorFilter.addEventListener("focus", () => {
      scheduleColorSearch(els.colorFilter.value || "");
    });
  }

  if (els.colorDropdown) {
    els.colorDropdown.addEventListener("mousedown", (event) => {
      const btn = event.target.closest("[data-color-index]");
      if (!btn) return;
      event.preventDefault();
      const items = JSON.parse(els.colorDropdown.dataset.items || "[]");
      const item = items[Number(btn.getAttribute("data-color-index"))];
      if (item) setColorFilter(item, { runSearch: true });
    });
  }

  document.addEventListener("click", (event) => {
    if (!event.target.closest('[data-ac="color"]')) {
      hideDropdown(els.colorDropdown);
    }
  });

  els.results.addEventListener("click", (event) => {
    const photo = event.target.closest("img.card-photo");
    if (photo && els.results.contains(photo)) {
      event.preventDefault();
      togglePhotoZoom(photo);
      return;
    }
    const btn = event.target.closest("[data-add]");
    if (!btn || btn.disabled) return;
    try {
      const item = JSON.parse(decodeURIComponent(btn.getAttribute("data-add")));
      addToCart(item);
      updateCartIndicators();
      btn.classList.remove("is-flash");
      // force reflow so repeated taps still animate
      void btn.offsetWidth;
      btn.classList.add("is-flash");
      window.setTimeout(() => btn.classList.remove("is-flash"), 280);
    } catch {
      showToast("Не вдалося додати товар");
    }
  });

  els.cartList.addEventListener("click", (event) => {
    const photo = event.target.closest("img.card-photo");
    if (photo && els.cartList.contains(photo)) {
      event.preventDefault();
      togglePhotoZoom(photo);
      return;
    }
    const cart = loadCart();
    const dec = event.target.closest("[data-dec]");
    const inc = event.target.closest("[data-inc]");
    const del = event.target.closest("[data-del]");

    if (dec) {
      const i = Number(dec.dataset.dec);
      cart[i].qty = Math.max(1, (cart[i].qty || 1) - 1);
      saveCart(cart);
      renderCart();
      return;
    }
    if (inc) {
      const i = Number(inc.dataset.inc);
      if (inc.disabled || !canAddMore(cart[i], cart[i].qty || 1)) {
        const max = stockNumber(cart[i]?.stock);
        showToast(max === null ? "Ліміт кількості" : `Доступно лише ${max} шт.`);
        return;
      }
      cart[i].qty = clampQtyToStock(cart[i], (cart[i].qty || 1) + 1);
      saveCart(cart);
      renderCart();
      return;
    }
    if (del) {
      const i = Number(del.dataset.del);
      cart.splice(i, 1);
      saveCart(cart);
      renderCart();
    }
  });

  if (els.photoZoomBackdrop) {
    els.photoZoomBackdrop.addEventListener("click", () => closePhotoZoom());
  }

  document.querySelectorAll("#mainTabs [data-tab]").forEach((tab) => {
    tab.addEventListener("click", () => switchTab(tab.dataset.tab));
  });

  els.cartChip.addEventListener("click", () => switchTab("cart"));
  if (els.settingsChip) {
    els.settingsChip.addEventListener("click", () => switchTab("settings"));
  }
  els.checkoutBtn.addEventListener("click", openCheckout);
  els.checkoutBack.addEventListener("click", () => switchTab("cart"));

  if (els.notifyShippingEvents) {
    els.notifyShippingEvents.addEventListener("change", () => {
      saveDropperNotifyShippingSetting(els.notifyShippingEvents.checked);
    });
  }

  els.phone.addEventListener("keydown", (event) => {
    if (event.key === "Backspace" || event.key === "Delete") {
      event.preventDefault();
      if (phoneDigits.length > 3) {
        setPhoneDigits(phoneDigits.slice(0, -1));
      } else {
        resetPhoneField();
      }
      return;
    }

    if (/^\d$/.test(event.key)) {
      event.preventDefault();
      if (phoneDigits.length < PHONE_MAX_DIGITS) {
        setPhoneDigits(phoneDigits + event.key);
      }
      return;
    }

    // Дозволяємо службові клавіші (Tab, стрілки тощо)
    if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
    }
  });

  els.phone.addEventListener("beforeinput", (event) => {
    // Мобільні клавіатури часто шлють цифри через beforeinput
    if (event.inputType === "insertText" && event.data && /^\d+$/.test(event.data)) {
      event.preventDefault();
      setPhoneDigits(phoneDigits + event.data);
      return;
    }
    if (
      event.inputType === "deleteContentBackward" ||
      event.inputType === "deleteContentForward"
    ) {
      event.preventDefault();
      if (phoneDigits.length > 3) {
        setPhoneDigits(phoneDigits.slice(0, -1));
      } else {
        resetPhoneField();
      }
    }
  });

  els.phone.addEventListener("paste", (event) => {
    event.preventDefault();
    const text = event.clipboardData?.getData("text") || "";
    setPhoneDigits(text);
  });

  els.phone.addEventListener("focus", () => {
    if (phoneDigits.length <= 3) {
      resetPhoneField();
    } else {
      setPhoneDigits(phoneDigits);
    }
  });

  els.ttnNumber.addEventListener("input", () => {
    const digits = els.ttnNumber.value.replace(/\D/g, "");
    if (els.ttnNumber.value !== digits) {
      els.ttnNumber.value = digits;
    }
  });

  els.ttnNumber.addEventListener("paste", (event) => {
    event.preventDefault();
    const text = event.clipboardData?.getData("text") || "";
    els.ttnNumber.value = text.replace(/\D/g, "");
  });

  els.ttnNumber.addEventListener("keydown", (event) => {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key.length === 1 && !/\d/.test(event.key)) {
      event.preventDefault();
    }
  });

  if (els.rmpNumber) {
    els.rmpNumber.addEventListener("input", () => {
      const next = normalizeRmpNumber(els.rmpNumber.value);
      if (els.rmpNumber.value !== next) {
        const pos = els.rmpNumber.selectionStart;
        els.rmpNumber.value = next;
        try {
          els.rmpNumber.setSelectionRange(pos, pos);
        } catch (_e) {
          /* ignore */
        }
      }
    });
    els.rmpNumber.addEventListener("blur", () => {
      const next = normalizeRmpNumber(els.rmpNumber.value);
      els.rmpNumber.value = next === "RMP-" ? "" : next;
    });
  }

  els.city.addEventListener("input", () => {
    clearCitySelection({ keepText: true });
    scheduleCitySearch(els.city.value);
  });

  els.city.addEventListener("focus", () => {
    if (els.city.value.trim().length >= 2 && !npState.city) {
      scheduleCitySearch(els.city.value);
    }
  });

  els.cityDropdown.addEventListener("mousedown", (event) => {
    const btn = event.target.closest("[data-city-index]");
    if (!btn) return;
    event.preventDefault();
    try {
      const items = JSON.parse(els.cityDropdown.dataset.items || "[]");
      const item = items[Number(btn.dataset.cityIndex)];
      if (item) selectCity(item);
    } catch {
      showToast("Не вдалося обрати місто");
    }
  });

  els.warehouse.addEventListener("input", () => {
    clearWarehouseSelection({ keepText: true });
    scheduleWarehouseSearch(els.warehouse.value);
  });

  els.warehouse.addEventListener("focus", () => {
    if (!els.warehouse.disabled) {
      scheduleWarehouseSearch(els.warehouse.value || "");
    }
  });

  els.warehouseDropdown.addEventListener("mousedown", (event) => {
    const btn = event.target.closest("[data-wh-index]");
    if (!btn) return;
    event.preventDefault();
    try {
      const items = JSON.parse(els.warehouseDropdown.dataset.items || "[]");
      const item = items[Number(btn.dataset.whIndex)];
      if (item) selectWarehouse(item);
    } catch {
      showToast("Не вдалося обрати відділення");
    }
  });

  els.street.addEventListener("input", () => {
    clearStreetSelection({ keepText: true });
    scheduleStreetSearch(els.street.value);
  });

  els.street.addEventListener("focus", () => {
    if (!els.street.disabled && els.street.value.trim().length >= 2 && !npState.street) {
      scheduleStreetSearch(els.street.value);
    }
  });

  els.streetDropdown.addEventListener("mousedown", (event) => {
    const btn = event.target.closest("[data-street-index]");
    if (!btn) return;
    event.preventDefault();
    try {
      const items = JSON.parse(els.streetDropdown.dataset.items || "[]");
      const item = items[Number(btn.dataset.streetIndex)];
      if (item) selectStreet(item);
    } catch {
      showToast("Не вдалося обрати вулицю");
    }
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest('[data-ac="city"]')) {
      hideDropdown(els.cityDropdown);
    }
    if (!event.target.closest('[data-ac="warehouse"]')) {
      hideDropdown(els.warehouseDropdown);
    }
    if (!event.target.closest('[data-ac="street"]')) {
      hideDropdown(els.streetDropdown);
    }
  });

  function bindFilePicker(inputEl, nameEl) {
    if (!inputEl || !nameEl) return;
    const emptyText = nameEl.dataset.empty || "Файл не обрано";
    const sync = () => {
      const file = inputEl.files && inputEl.files[0];
      if (file) {
        nameEl.textContent = file.name;
        nameEl.classList.add("is-selected");
      } else {
        nameEl.textContent = emptyText;
        nameEl.classList.remove("is-selected");
      }
    };
    inputEl.addEventListener("change", sync);
    sync();
  }

  bindFilePicker(els.ttnPdf, els.ttnPdfName);

  els.checkoutForm.addEventListener("change", (event) => {
    if (event.target.name === "deliveryMethod") syncDeliveryFields();
    if (event.target.id === "ownTtn") {
      if (!isFlagEnabled(dropperSettings.allow_cod, true) && !event.target.checked) {
        event.target.checked = true;
        showToast("Відправлення накладним платежем заблоковано постачальником", 5000);
      }
      syncPaymentAndTtn();
      return;
    }
    if (
      event.target.name === "paymentMethod" ||
      event.target.name === "ownTtnCarrier"
    ) {
      syncPaymentAndTtn();
    }
  });

  if (els.ownTtn) {
    els.ownTtn.addEventListener("click", (event) => {
      if (!isFlagEnabled(dropperSettings.allow_cod, true) && els.ownTtn.checked) {
        // Клік намагається вимкнути (буде unchecked після click) — блокуємо
        // На click checked ще старий стан: якщо зараз true і клікають — стане false
        // Тому якщо allow_cod off і тумблер увімкнений — не даємо вимкнути
        event.preventDefault();
        els.ownTtn.checked = true;
        showToast("Відправлення накладним платежем заблоковано постачальником", 5000);
      }
    });
  }

  els.checkoutForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = collectCheckoutData();
    const error = validateCheckout(data);
    if (error) {
      setCheckoutError(error);
      return;
    }
    setCheckoutError("");
    openConfirmView(data);
  });

  if (els.confirmBack) {
    els.confirmBack.addEventListener("click", () => {
      if (els.confirmView) els.confirmView.classList.add("hidden");
      els.checkoutView.classList.remove("hidden");
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  if (els.confirmSubmit) {
    els.confirmSubmit.addEventListener("click", () => {
      submitOrder();
    });
  }

  function ownerAuthParams() {
    const chatId = currentTelegramChatId();
    const userId = currentTelegramUser().user_id;
    const params = new URLSearchParams();
    if (chatId) params.set("owner_chat_id", chatId);
    if (userId) params.set("owner_user_id", userId);
    return params.toString();
  }

  function ownerAuthBody(extra = {}) {
    return {
      owner_chat_id: currentTelegramChatId(),
      owner_user_id: currentTelegramUser().user_id,
      ...extra,
    };
  }

  function staffRoleLabel(role) {
    const map = {
      admin: "Адміністратор",
      manager: "Менеджер",
      warehouse: "Комірник",
    };
    return map[role] || role;
  }

  function setOwnerTab(tabName) {
    const allowed = new Set([
      "droppers",
      "staff",
      "balances",
      "returns",
      "settings",
      "order",
      "blacklist",
    ]);
    const name = allowed.has(tabName) ? tabName : "droppers";
    if (els.ownerTabs) {
      els.ownerTabs.querySelectorAll("[data-owner-tab]").forEach((btn) => {
        btn.classList.toggle("active", btn.getAttribute("data-owner-tab") === name);
      });
    }
    if (els.ownerTabDroppers) {
      els.ownerTabDroppers.classList.toggle("hidden", name !== "droppers");
    }
    if (els.ownerTabStaff) {
      els.ownerTabStaff.classList.toggle("hidden", name !== "staff");
    }
    if (els.ownerTabBalances) {
      els.ownerTabBalances.classList.toggle("hidden", name !== "balances");
    }
    if (els.ownerTabReturns) {
      els.ownerTabReturns.classList.toggle("hidden", name !== "returns");
    }
    if (els.ownerTabSettings) {
      els.ownerTabSettings.classList.toggle("hidden", name !== "settings");
    }
    if (els.ownerTabOrder) {
      els.ownerTabOrder.classList.toggle("hidden", name !== "order");
    }
    if (els.ownerTabBlacklist) {
      els.ownerTabBlacklist.classList.toggle("hidden", name !== "blacklist");
    }

    const showOrder = name === "order";
    if (els.orderMain) els.orderMain.classList.toggle("hidden", !showOrder);
    if (els.mainTabs) els.mainTabs.classList.toggle("hidden", !showOrder);
    setTopbarOrderVisible(showOrder);

    if (name === "balances") {
      renderOwnerBalances();
    }
    if (name === "returns") {
      renderOwnerReturns();
    }
    if (name === "blacklist") {
      renderOwnerBlacklist();
    }
    if (name === "settings") {
      loadGeneralSettings();
    }
    if (showOrder) {
      loadColorOptions();
      loadDropperSettings().then(() => {
        syncPaymentAndTtn();
        updateCartIndicators();
        switchTab("catalog");
      });
    }
  }

  function formatLedgerAmount(amount) {
    const n = Number(amount) || 0;
    const sign = n > 0 ? "+" : "";
    const cls = n >= 0 ? "ledger-amount-plus" : "ledger-amount-minus";
    return `<span class="${cls}">${sign}${formatMoney(n)}</span>`;
  }

  function ledgerTypeLabel(entryType) {
    const key = String(entryType || "").trim();
    if (key === "referral_credit") return "Реферальне нарахування";
    if (key === "balance_payment") return "Оплата замовлення з балансу";
    if (key === "prepay_overage_debit") return "Списання (передплата понад «Дроп ціна»)";
    if (key === "cod_profit_credit") return "Прибуток з наложки (посилку отримано)";
    if (key === "cod_profit_reversal") return "Сторно прибутку (повернення)";
    if (key === "return_delivery_debit") return "Доставка при відмові/поверненні";
    if (key === "return_goods_credit") return "Повернення товару";
    if (key === "referral_reversal") return "Сторно рефералу";
    if (key === "manual_credit") return "Ручне нарахування";
    if (key === "manual_debit") return "Ручне списання";
    return key || "Операція";
  }

  function renderLedgerRow(r) {
    const title = r.title || ledgerTypeLabel(r.entry_type);
    const typeLabel = ledgerTypeLabel(r.entry_type);
    const orderNo = String(r.related_order_id || "").trim();
    const sourceName = String(r.related_dropper_name || "").trim();
    const when = formatOrderDate(r.created_at) || r.created_at || "";
    const details = [];
    if (typeLabel && typeLabel !== title) details.push(typeLabel);
    if (orderNo) details.push(`Замовлення: ${orderNo}`);
    if (sourceName) details.push(`Від реферала: ${sourceName}`);
    if (r.note) details.push(r.note);
    return `
      <article class="owner-card ledger-card">
        <div class="ledger-card-top">
          <div class="owner-card-title">${escapeHtml(title)}</div>
          <div class="ledger-amount">${formatLedgerAmount(r.amount)}</div>
        </div>
        ${
          details.length
            ? `<div class="meta-soft">${details.map((d) => escapeHtml(d)).join("<br/>")}</div>`
            : ""
        }
        <div class="meta-soft">${escapeHtml(when)}</div>
      </article>`;
  }

  async function renderBalanceView() {
    if (!els.balanceView) return;
    els.balanceHero.textContent = "…";
    if (els.balanceStats) els.balanceStats.innerHTML = "";
    els.balanceLedger.innerHTML = `<div class="ac-loading">Завантаження...</div>`;
    try {
      const chatId = effectiveDropperChatId();
      const response = await fetch(
        `/api/dropper/balance?chat_id=${encodeURIComponent(chatId)}`
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Помилка балансу");
      const balance = Number(data.balance || 0);
      els.balanceHero.textContent = formatMoney(balance);
      if (els.balanceConditional) {
        const condBal = Number(
          data.conditional_balance != null ? data.conditional_balance : balance
        );
        const delta = Number(data.conditional_delta || 0);
        if (Math.abs(delta) > 0.009) {
          els.balanceConditional.classList.remove("hidden");
          els.balanceConditional.textContent = `Умовно: ${formatMoney(condBal)}`;
        } else {
          els.balanceConditional.classList.add("hidden");
          els.balanceConditional.textContent = "";
        }
      }
      const dropper = data.dropper || {};
      const programOn = Boolean(dropper.referral_program_enabled);
      const spendRoom = Number(data.spend_room != null ? data.spend_room : 0);
      const refTotal = Number(data.referral_earned_total || 0);
      const debited = Number(data.debited_total || 0);
      const credited = Number(data.credited_total || 0);
      if (els.balanceStats) {
        const bits = [];
        if (programOn) {
          bits.push(
            `<div class="balance-stat"><span class="balance-stat-label">Реферально нараховано</span><span class="balance-stat-value">${escapeHtml(
              formatMoney(refTotal)
            )}</span></div>`
          );
        }
        bits.push(
          `<div class="balance-stat"><span class="balance-stat-label">Усього нараховано</span><span class="balance-stat-value ledger-amount-plus">+${escapeHtml(
            formatMoney(credited)
          )}</span></div>`,
          `<div class="balance-stat"><span class="balance-stat-label">Усього списано</span><span class="balance-stat-value ledger-amount-minus">${escapeHtml(
            formatMoney(-Math.abs(debited))
          )}</span></div>`
        );
        if (dropper.allow_negative_balance) {
          bits.push(
            `<div class="balance-stat"><span class="balance-stat-label">Доступно до списання</span><span class="balance-stat-value">${escapeHtml(
              formatMoney(spendRoom)
            )}</span></div>`
          );
        }
        els.balanceStats.innerHTML = bits.join("");
      }
      if (els.balanceReferralTotal) {
        els.balanceReferralTotal.textContent = "";
      }
      if (els.balanceHint) {
        els.balanceHint.textContent =
          data.note ||
          "Фактичний баланс змінюється після отримання посилки. «Умовно» — прогноз з урахуванням посилок у дорозі.";
      }
      const rows = data.ledger || [];
      els.balanceLedger.innerHTML = rows.length
        ? rows.map(renderLedgerRow).join("")
        : `<div class="empty">${
            programOn
              ? "Поки немає операцій по балансу. Тут з’являться списання, нарахування та реферали."
              : "Поки немає операцій по балансу. Тут з’являться списання та нарахування."
          }</div>`;
    } catch (error) {
      els.balanceHero.textContent = "—";
      if (els.balanceConditional) {
        els.balanceConditional.classList.add("hidden");
        els.balanceConditional.textContent = "";
      }
      if (els.balanceStats) els.balanceStats.innerHTML = "";
      els.balanceLedger.innerHTML = `<div class="form-error">${escapeHtml(
        error.message || "Помилка"
      )}</div>`;
    }
  }

  async function renderDropperSettingsView() {
    if (!els.dropperSettingsView) return;
    if (els.dropperSettingsStatus) {
      els.dropperSettingsStatus.classList.add("hidden");
      els.dropperSettingsStatus.textContent = "";
    }
    await loadDropperSettings();
    if (els.notifyShippingEvents) {
      els.notifyShippingEvents.checked = Boolean(dropperSettings.notify_shipping_events);
    }
  }

  async function saveDropperNotifyShippingSetting(enabled) {
    const chatId = effectiveDropperChatId();
    if (!chatId) {
      showToast("Немає chat_id дроппера");
      return;
    }
    if (els.dropperSettingsStatus) {
      els.dropperSettingsStatus.textContent = "Збереження…";
      els.dropperSettingsStatus.classList.remove("hidden");
      els.dropperSettingsStatus.style.color = "";
    }
    try {
      const response = await fetch("/api/dropper/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          user_id: currentTelegramUser().user_id,
          notify_shipping_events: Boolean(enabled),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Не вдалося зберегти");
      dropperSettings.notify_shipping_events = Boolean(
        (data.dropper && data.dropper.notify_shipping_events) ?? enabled
      );
      if (els.notifyShippingEvents) {
        els.notifyShippingEvents.checked = dropperSettings.notify_shipping_events;
      }
      if (els.dropperSettingsStatus) {
        els.dropperSettingsStatus.textContent = "Збережено";
        els.dropperSettingsStatus.style.color = "var(--ok)";
      }
      showToast("Налаштування збережено");
    } catch (error) {
      if (els.notifyShippingEvents) {
        els.notifyShippingEvents.checked = Boolean(dropperSettings.notify_shipping_events);
      }
      if (els.dropperSettingsStatus) {
        els.dropperSettingsStatus.textContent = error.message || "Помилка збереження";
        els.dropperSettingsStatus.style.color = "var(--danger)";
      }
      showToast(error.message || "Помилка збереження");
    }
  }

  const senderNpState = {
    city: null,
    warehouse: null,
    cityTimer: null,
    warehouseTimer: null,
    cityReq: 0,
    warehouseReq: 0,
  };

  let generalSettingsState = {
    np_api_keys: [],
    payment_requisites: [],
    sheet_columns: [],
  };

  function newNpKeyRow(data = {}) {
    return {
      id: data.id || `k${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
      label: data.label || "",
      api_key: data.api_key || "",
      enabled: Boolean(data.enabled),
    };
  }

  function newPaymentRequisiteRow(data = {}) {
    const kind = data.kind === "card" ? "card" : "fop";
    return {
      id: data.id || `r${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
      kind,
      label: data.label || "",
      recipient: data.recipient || "",
      edrpou: data.edrpou || "",
      iban: data.iban || "",
      card_number: data.card_number || "",
      bank: data.bank || "",
      purpose: data.purpose || "",
      enabled: Boolean(data.enabled),
    };
  }

  function renderNpApiKeys() {
    if (!els.npApiKeysList) return;
    const keys = generalSettingsState.np_api_keys || [];
    if (!keys.length) {
      generalSettingsState.np_api_keys = [newNpKeyRow({ label: "Кабінет 1" })];
    }
    els.npApiKeysList.innerHTML = generalSettingsState.np_api_keys
      .map(
        (row, index) => `
      <div class="np-key-row" data-np-key-index="${index}">
        <div class="np-key-fields">
          <label class="field compact-field">
            <span class="field-label">Назва кабінету</span>
            <input type="text" data-np-field="label" placeholder="Напр. Кабінет 1" value="${escapeHtml(
              row.label || ""
            )}" autocomplete="off" />
          </label>
          <label class="field compact-field">
            <span class="field-label">API-ключ</span>
            <input type="password" data-np-field="api_key" placeholder="Вставте ключ Нової Пошти" value="${escapeHtml(
              row.api_key || ""
            )}" autocomplete="off" />
          </label>
        </div>
        <div class="np-key-footer">
          <label class="np-key-enabled">
            <input type="checkbox" data-np-field="enabled" ${row.enabled ? "checked" : ""} />
            <span>Основний для створення ТТН</span>
          </label>
          <button type="button" class="btn danger" data-np-remove="${index}">Видалити</button>
        </div>
      </div>`
      )
      .join("");
  }

  function renderPaymentRequisites() {
    if (!els.paymentRequisitesList) return;
    if (!generalSettingsState.payment_requisites?.length) {
      generalSettingsState.payment_requisites = [
        newPaymentRequisiteRow({ label: "ФОП / рахунок 1", kind: "fop" }),
      ];
    }
    els.paymentRequisitesList.innerHTML = generalSettingsState.payment_requisites
      .map((row, index) => {
        const kind = row.kind === "card" ? "card" : "fop";
        const fopHidden = kind === "card" ? "hidden" : "";
        const cardHidden = kind === "fop" ? "hidden" : "";
        return `
      <div class="np-key-row" data-req-index="${index}">
        <div class="req-key-fields">
          <label class="field compact-field">
            <span class="field-label">Тип</span>
            <select data-req-field="kind">
              <option value="fop" ${kind === "fop" ? "selected" : ""}>ФОП / IBAN</option>
              <option value="card" ${kind === "card" ? "selected" : ""}>Звичайна картка</option>
            </select>
          </label>
          <label class="field compact-field">
            <span class="field-label">Назва (для вас)</span>
            <input type="text" data-req-field="label" placeholder="Напр. ФОП Приват" value="${escapeHtml(
              row.label || ""
            )}" autocomplete="off" />
          </label>
          <label class="field compact-field req-span-2">
            <span class="field-label">Отримувач</span>
            <input type="text" data-req-field="recipient" placeholder="ПІБ або назва ФОП" value="${escapeHtml(
              row.recipient || ""
            )}" autocomplete="off" />
          </label>
          <label class="field compact-field ${fopHidden}" data-req-show="fop">
            <span class="field-label">ЄДРПОУ</span>
            <input type="text" data-req-field="edrpou" placeholder="XXXXXXXXXX" value="${escapeHtml(
              row.edrpou || ""
            )}" autocomplete="off" />
          </label>
          <label class="field compact-field ${fopHidden}" data-req-show="fop">
            <span class="field-label">IBAN</span>
            <input type="text" data-req-field="iban" placeholder="UA..." value="${escapeHtml(
              row.iban || ""
            )}" autocomplete="off" />
          </label>
          <label class="field compact-field req-span-2 ${cardHidden}" data-req-show="card">
            <span class="field-label">Номер картки</span>
            <input type="text" data-req-field="card_number" placeholder="XXXX XXXX XXXX XXXX" value="${escapeHtml(
              row.card_number || ""
            )}" autocomplete="off" />
          </label>
          <label class="field compact-field">
            <span class="field-label">Банк</span>
            <input type="text" data-req-field="bank" placeholder="АТ КБ «ПРИВАТБАНК»" value="${escapeHtml(
              row.bank || ""
            )}" autocomplete="off" />
          </label>
          <label class="field compact-field">
            <span class="field-label">Призначення платежу</span>
            <input type="text" data-req-field="purpose" placeholder="Оплата замовлення" value="${escapeHtml(
              row.purpose || ""
            )}" autocomplete="off" />
          </label>
        </div>
        <div class="np-key-footer">
          <label class="np-key-enabled">
            <input type="checkbox" data-req-field="enabled" ${row.enabled ? "checked" : ""} />
            <span>Показувати дропперам</span>
          </label>
          <button type="button" class="btn danger" data-req-remove="${index}">Видалити</button>
        </div>
      </div>`;
      })
      .join("");
  }

  function collectNpApiKeysFromDom() {
    if (!els.npApiKeysList) return generalSettingsState.np_api_keys || [];
    const rows = [...els.npApiKeysList.querySelectorAll(".np-key-row")];
    return rows.map((row, index) => {
      const prev = generalSettingsState.np_api_keys[index] || newNpKeyRow();
      return {
        id: prev.id,
        label: row.querySelector('[data-np-field="label"]')?.value?.trim() || "",
        api_key: row.querySelector('[data-np-field="api_key"]')?.value?.trim() || "",
        enabled: Boolean(row.querySelector('[data-np-field="enabled"]')?.checked),
      };
    });
  }

  function collectPaymentRequisitesFromDom() {
    if (!els.paymentRequisitesList) return generalSettingsState.payment_requisites || [];
    const rows = [...els.paymentRequisitesList.querySelectorAll("[data-req-index]")];
    return rows.map((row, index) => {
      const prev = generalSettingsState.payment_requisites[index] || newPaymentRequisiteRow();
      const kind =
        row.querySelector('[data-req-field="kind"]')?.value === "card" ? "card" : "fop";
      return {
        id: prev.id,
        kind,
        label: row.querySelector('[data-req-field="label"]')?.value?.trim() || "",
        recipient: row.querySelector('[data-req-field="recipient"]')?.value?.trim() || "",
        edrpou: row.querySelector('[data-req-field="edrpou"]')?.value?.trim() || "",
        iban: row.querySelector('[data-req-field="iban"]')?.value?.trim() || "",
        card_number:
          row.querySelector('[data-req-field="card_number"]')?.value?.trim() || "",
        bank: row.querySelector('[data-req-field="bank"]')?.value?.trim() || "",
        purpose: row.querySelector('[data-req-field="purpose"]')?.value?.trim() || "",
        enabled: Boolean(row.querySelector('[data-req-field="enabled"]')?.checked),
      };
    });
  }

  function fillGeneralSettingsForm(settings, sheetColumns) {
    generalSettingsState.np_api_keys = (settings.np_api_keys || []).map((k) => newNpKeyRow(k));
    if (!generalSettingsState.np_api_keys.length) {
      generalSettingsState.np_api_keys = [newNpKeyRow({ label: "Кабінет 1" })];
    }
    generalSettingsState.payment_requisites = (settings.payment_requisites || []).map((r) =>
      newPaymentRequisiteRow(r)
    );
    if (!generalSettingsState.payment_requisites.length) {
      generalSettingsState.payment_requisites = [
        newPaymentRequisiteRow({ label: "ФОП / рахунок 1", kind: "fop" }),
      ];
    }
    generalSettingsState.sheet_columns = sheetColumns || [];
    renderNpApiKeys();
    renderPaymentRequisites();

    const city = settings.sender_city || {};
    const wh = settings.sender_warehouse || {};
    const parcel = settings.parcel_defaults || {};
    if (els.senderCity) els.senderCity.value = city.label || "";
    if (els.senderCityRef) els.senderCityRef.value = city.city_ref || "";
    if (els.senderSettlementRef) els.senderSettlementRef.value = city.settlement_ref || "";
    if (els.senderWarehouse) els.senderWarehouse.value = wh.label || "";
    if (els.senderWarehouseRef) els.senderWarehouseRef.value = wh.ref || "";
    if (els.senderWarehouseNumber) els.senderWarehouseNumber.value = wh.number || "";
    senderNpState.city = city.city_ref
      ? {
          label: city.label || "",
          city_ref: city.city_ref || "",
          settlement_ref: city.settlement_ref || "",
        }
      : null;
    senderNpState.warehouse = wh.ref
      ? { label: wh.label || "", ref: wh.ref || "", number: wh.number || "" }
      : null;

    if (els.parcelWeight) els.parcelWeight.value = parcel.weight_kg ?? 0.5;
    if (els.parcelLength) els.parcelLength.value = parcel.length_cm ?? 30;
    if (els.parcelWidth) els.parcelWidth.value = parcel.width_cm ?? 20;
    if (els.parcelHeight) els.parcelHeight.value = parcel.height_cm ?? 10;
    if (els.parcelSeats) els.parcelSeats.value = parcel.seats_amount ?? 1;
    if (els.parcelDescription) els.parcelDescription.value = parcel.description || "Товар";
    if (els.ordersSheetUrl) {
      els.ordersSheetUrl.value =
        settings.orders_spreadsheet_url ||
        (settings.orders_spreadsheet_id
          ? `https://docs.google.com/spreadsheets/d/${settings.orders_spreadsheet_id}/edit`
          : "");
    }
    if (els.ordersSheetColumnsHint) {
      const cols = generalSettingsState.sheet_columns || [];
      els.ordersSheetColumnsHint.innerHTML = cols.length
        ? `<b>Колонки листа «Заказы»:</b> ${escapeHtml(cols.join(" · "))}`
        : "Колонки підвантажаться після збереження/відкриття.";
    }
  }

  async function loadGeneralSettings() {
    if (els.generalSettingsError) {
      els.generalSettingsError.classList.add("hidden");
      els.generalSettingsError.textContent = "";
    }
    if (els.generalSettingsOk) els.generalSettingsOk.classList.add("hidden");
    try {
      const response = await fetch(`/api/owner/settings?${ownerAuthParams()}`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Помилка налаштувань");
      }
      fillGeneralSettingsForm(data.settings || {}, data.sheet_columns || []);
      if (els.npWebhookHint) {
        const url = String(data.np_webhook_url || "").trim();
        if (url) {
          els.npWebhookHint.textContent = data.np_webhook_token_set
            ? `Webhook URL для кабінету НП: ${url}`
            : `Webhook URL: ${url} (додайте NP_WEBHOOK_TOKEN у Render для захисту)`;
          els.npWebhookHint.classList.remove("hidden");
        } else {
          els.npWebhookHint.textContent =
            "Задайте WEBAPP_URL і NP_WEBHOOK_TOKEN у Render — тут зʼявиться URL вебхука статусів ТТН.";
          els.npWebhookHint.classList.remove("hidden");
        }
      }
    } catch (error) {
      if (els.generalSettingsError) {
        els.generalSettingsError.textContent = error.message || "Помилка";
        els.generalSettingsError.classList.remove("hidden");
      }
    }
  }

  function collectGeneralSettingsPayload() {
    return {
      ...ownerAuthBody(),
      np_api_keys: collectNpApiKeysFromDom(),
      payment_requisites: collectPaymentRequisitesFromDom(),
      sender_city: {
        label: els.senderCity?.value?.trim() || "",
        city_ref: els.senderCityRef?.value?.trim() || "",
        settlement_ref: els.senderSettlementRef?.value?.trim() || "",
      },
      sender_warehouse: {
        label: els.senderWarehouse?.value?.trim() || "",
        ref: els.senderWarehouseRef?.value?.trim() || "",
        number: els.senderWarehouseNumber?.value?.trim() || "",
      },
      parcel_defaults: {
        weight_kg: Number(els.parcelWeight?.value || 0.5),
        length_cm: Number(els.parcelLength?.value || 30),
        width_cm: Number(els.parcelWidth?.value || 20),
        height_cm: Number(els.parcelHeight?.value || 10),
        seats_amount: Number(els.parcelSeats?.value || 1),
        description: els.parcelDescription?.value?.trim() || "Товар",
      },
      orders_spreadsheet_url: els.ordersSheetUrl?.value?.trim() || "",
    };
  }

  async function searchSenderCities(query) {
    const reqId = ++senderNpState.cityReq;
    showDropdownMessage(els.senderCityDropdown, "Шукаємо...", "ac-loading");
    try {
      const response = await fetch(
        `/api/np/settlements?q=${encodeURIComponent(query)}&limit=20`
      );
      const data = await response.json();
      if (reqId !== senderNpState.cityReq) return;
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
      }
      const items = data.items || [];
      if (!items.length) {
        showDropdownMessage(els.senderCityDropdown, "Нічого не знайдено");
        return;
      }
      els.senderCityDropdown.innerHTML = items
        .map((item, index) => {
          const title = item.label || item.present || "";
          return `<button type="button" class="ac-option" data-sender-city-index="${index}"><span>${escapeHtml(
            title
          )}</span></button>`;
        })
        .join("");
      els.senderCityDropdown.dataset.items = JSON.stringify(items);
      els.senderCityDropdown.classList.remove("hidden");
    } catch (error) {
      if (reqId !== senderNpState.cityReq) return;
      showDropdownMessage(els.senderCityDropdown, error.message || "Помилка");
    }
  }

  async function searchSenderWarehouses(query) {
    const cityRef = senderNpState.city?.city_ref || els.senderCityRef?.value;
    if (!cityRef) return;
    const reqId = ++senderNpState.warehouseReq;
    showDropdownMessage(els.senderWarehouseDropdown, "Шукаємо...", "ac-loading");
    try {
      const q = normalizeWarehouseQuery(query);
      const response = await fetch(
        `/api/np/warehouses?city_ref=${encodeURIComponent(cityRef)}&q=${encodeURIComponent(
          q
        )}&limit=20`
      );
      const data = await response.json();
      if (reqId !== senderNpState.warehouseReq) return;
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
      }
      const items = data.items || [];
      if (!items.length) {
        showDropdownMessage(els.senderWarehouseDropdown, "Нічого не знайдено");
        return;
      }
      els.senderWarehouseDropdown.innerHTML = items
        .map((item, index) => {
          const title = item.label || item.description || "";
          return `<button type="button" class="ac-option" data-sender-wh-index="${index}"><span>${escapeHtml(
            title
          )}</span></button>`;
        })
        .join("");
      els.senderWarehouseDropdown.dataset.items = JSON.stringify(items);
      els.senderWarehouseDropdown.classList.remove("hidden");
    } catch (error) {
      if (reqId !== senderNpState.warehouseReq) return;
      showDropdownMessage(els.senderWarehouseDropdown, error.message || "Помилка");
    }
  }

  function buyoutBadgeHtml(buyout) {
    const info = buyout || {};
    const percent = info.percent;
    if (percent == null || !Number.isFinite(Number(percent))) {
      return `<span class="buyout-badge buyout-none" title="Ще немає завершених замовлень">—</span>`;
    }
    const tier = String(info.tier || "");
    const label = String(info.label || "");
    const pct = Number(percent);
    return `<span class="buyout-badge buyout-${escapeHtml(tier)}" title="${escapeHtml(
      label
    )}"><b>${escapeHtml(String(pct))}%</b> <span class="buyout-label">${escapeHtml(
      label
    )}</span></span>`;
  }

  async function renderOwnerReturns() {
    if (!els.ownerReturnsList) return;
    syncOwnerReturnsTabs();
    els.ownerReturnsList.innerHTML = `<div class="ac-loading">Завантаження...</div>`;
    try {
      const params = new URLSearchParams(ownerAuthParams());
      params.set("bucket", ownerReturnsState.bucket || "awaiting_receipt");
      params.set("limit", "200");
      const response = await fetch(`/api/owner/returns?${params.toString()}`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
      }
      ownerReturnsState.counts = data.counts || {};
      syncOwnerReturnsTabs();
      const items = data.items || [];
      const emptyByBucket = {
        awaiting_receipt: "Немає повернень у дорозі",
        awaiting_confirm: "Немає повернень на підтвердження",
        closed: "Архів порожній",
      };
      if (!items.length) {
        els.ownerReturnsList.innerHTML = `<div class="empty">${escapeHtml(
          emptyByBucket[ownerReturnsState.bucket] || "Немає заявок на повернення"
        )}</div>`;
        return;
      }
      els.ownerReturnsList.className = "results owner-returns";
      els.ownerReturnsList.innerHTML = items
        .map((row) => {
          const ret = row.dropper_return || (row.payload && row.payload.dropper_return) || {};
          const st = normalizeReturnStatus(ret.status);
          const statusKind =
            st === "accepted"
              ? "return_accepted"
              : st === "awaiting_confirm"
                ? "return_pending"
                : "return_pending";
          let actionHtml = "";
          if (st === "awaiting_receipt") {
            actionHtml = `<button type="button" class="btn secondary" data-owner-return-received="${escapeHtml(
              String(row.id || "")
            )}">Позначити отриманим</button>`;
          } else if (st === "awaiting_confirm") {
            actionHtml = `<button type="button" class="btn primary" data-owner-return-accept="${escapeHtml(
              String(row.id || "")
            )}">Підтвержено</button>`;
          } else if (ret.accepted_at) {
            actionHtml = `<div class="meta-soft">Підтверджено: ${escapeHtml(
              formatOrderDate(ret.accepted_at) || ret.accepted_at
            )}${
              ret.refund_amount
                ? ` · товар +${escapeHtml(formatMoney(ret.refund_amount))}`
                : ""
            }</div>`;
          }
          const ttnStatus = ret.ttn_status
            ? `<div class="meta-soft">Статус зворотної ТТН: ${escapeHtml(
                ret.ttn_status
              )}</div>`
            : "";
          return `
          <article class="owner-return-card" data-return-order-id="${escapeHtml(
            String(row.id || "")
          )}">
            <div class="owner-return-card-head">
              <div>
                <div class="owner-card-title">${escapeHtml(row.order_number || "")}</div>
                <div class="meta">${escapeHtml(row.dropper_name || "—")}</div>
                <div class="meta-soft">${escapeHtml(
                  formatOrderDate(ret.created_at || row.created_at) || ""
                )}</div>
              </div>
              <div class="order-card-status status-${escapeHtml(statusKind)}">${escapeHtml(
                dropperReturnStatusLabel(st)
              )}</div>
            </div>
            <div class="meta">Тип: <b>${escapeHtml(dropperReturnTypeLabel(ret.type))}</b></div>
            <div class="meta">ТТН повернення: <b>${escapeHtml(ret.ttn_number || "—")}</b></div>
            <div class="meta">Оригінальна ТТН: ${escapeHtml(row.ttn_number || "—")}</div>
            <div class="meta">Дроп-ціна: <b>${escapeHtml(formatMoney(row.total || 0))}</b></div>
            ${ttnStatus}
            ${actionHtml}
          </article>`;
        })
        .join("");
    } catch (error) {
      els.ownerReturnsList.innerHTML = `<div class="form-error">${escapeHtml(
        error.message || "Помилка"
      )}</div>`;
    }
  }

  function syncOwnerReturnsTabs() {
    if (!els.ownerReturnsTabs) return;
    const counts = ownerReturnsState.counts || {};
    els.ownerReturnsTabs.querySelectorAll("[data-returns-bucket]").forEach((btn) => {
      const key = btn.getAttribute("data-returns-bucket") || "";
      btn.classList.toggle("active", key === ownerReturnsState.bucket);
      const n = Number(counts[key] || 0);
      const labels = {
        awaiting_receipt: "Очікують отримання",
        awaiting_confirm: "Очікують підтвердження",
        closed: "Закрито / Архів",
      };
      const base = labels[key] || key;
      btn.textContent = n > 0 ? `${base} (${n})` : base;
    });
  }

  async function markOwnerReturnReceived(orderId) {
    try {
      const response = await fetch(
        `/api/owner/returns/${encodeURIComponent(orderId)}/mark-received`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(ownerAuthBody()),
        }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
      }
      showToast("Повернення позначено отриманим");
      ownerReturnsState.bucket = "awaiting_confirm";
      await renderOwnerReturns();
    } catch (error) {
      showToast(error.message || "Помилка");
    }
  }

  async function acceptOwnerReturn(orderId) {
    try {
      const response = await fetch(
        `/api/owner/returns/${encodeURIComponent(orderId)}/accept`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(ownerAuthBody()),
        }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
      }
      const refund = Number(data.refund_amount || 0);
      showToast(
        refund > 0
          ? `Підтверджено · на баланс +${formatMoney(refund)}`
          : "Повернення підтверджено"
      );
      ownerReturnsState.bucket = "closed";
      await renderOwnerReturns();
    } catch (error) {
      showToast(error.message || "Помилка");
    }
  }

  async function renderOwnerBalances() {
    if (!els.ownerBalances) return;
    els.ownerBalances.innerHTML = `<div class="ac-loading">Завантаження...</div>`;
    if (els.ownerReferralHistory) {
      els.ownerReferralHistory.innerHTML = "";
    }
    try {
      const response = await fetch(`/api/owner/balances?${ownerAuthParams()}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Помилка");
      const items = data.items || [];
      els.ownerBalances.innerHTML = items.length
        ? items
            .map((row) => {
              const d = row.dropper || {};
              return `
            <article class="owner-card is-collapsed" data-balance-chat="${escapeHtml(
              d.chat_id || ""
            )}">
              <button type="button" class="owner-card-toggle" aria-expanded="false">
                <div class="owner-card-head">
                  <div class="owner-card-title-row">
                    <div class="owner-card-title">${escapeHtml(d.company_name || "")}</div>
                    ${buyoutBadgeHtml(row.buyout)}
                  </div>
                  <div class="meta">Баланс: <b>${escapeHtml(formatMoney(row.balance || 0))}</b></div>
                  <div class="meta balance-conditional-line">Умовно: <b>${escapeHtml(
                    formatMoney(
                      row.conditional_balance != null
                        ? row.conditional_balance
                        : row.balance || 0
                    )
                  )}</b></div>
                  <div class="meta">Отримано: <b>—</b></div>
                  <div class="meta">В дорозі: <b>${escapeHtml(
                    formatMoney(row.in_transit_drop_total || 0)
                  )}</b></div>
                  <div class="meta-soft">Реф. нараховано: ${escapeHtml(
                    formatMoney(row.referral_earned_total || 0)
                  )} · код ${escapeHtml(d.referral_code || "—")}</div>
                </div>
                <span class="owner-card-chevron" aria-hidden="true"></span>
              </button>
            </article>`;
            })
            .join("")
        : `<div class="empty">Немає дропперів</div>`;

      const history = data.referral_history || [];
      if (els.ownerReferralHistory) {
        els.ownerReferralHistory.innerHTML = history.length
          ? history
              .map(
                (r) => `
            <article class="owner-card">
              <div class="owner-card-title">${escapeHtml(r.beneficiary_name || "")}</div>
              <div class="meta">${formatLedgerAmount(r.amount)} · від ${escapeHtml(
                  r.source_name || "—"
                )}</div>
              <div class="meta-soft">${escapeHtml(r.note || "")}</div>
              <div class="meta-soft">${escapeHtml(r.created_at || "")}</div>
            </article>`
              )
              .join("")
          : `<div class="empty">Історія рефералів порожня — з’явиться після підтверджених замовлень.</div>`;
      }
    } catch (error) {
      els.ownerBalances.innerHTML = `<div class="form-error">${escapeHtml(
        error.message || "Помилка"
      )}</div>`;
    }
  }

  async function renderOwnerBlacklist() {
    if (!els.ownerBlacklist) return;
    els.ownerBlacklist.innerHTML = `<div class="ac-loading">Завантаження...</div>`;
    try {
      const response = await fetch(`/api/owner/blacklist?${ownerAuthParams()}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Помилка");
      blacklistState.items = data.items || [];
      if (els.blacklistSearch && !blacklistState.search) {
        blacklistState.search = (els.blacklistSearch.value || "").trim();
      }
      paintOwnerBlacklistList();
    } catch (error) {
      els.ownerBlacklist.innerHTML = `<div class="form-error">${escapeHtml(
        error.message || "Помилка"
      )}</div>`;
    }
  }

  function blacklistPhoneDigits(value) {
    return String(value || "").replace(/\D/g, "");
  }

  function filteredBlacklistItems() {
    const q = blacklistPhoneDigits(blacklistState.search);
    if (!q) return blacklistState.items.slice();
    return blacklistState.items.filter((row) => {
      const digits = blacklistPhoneDigits(row.phone_digits || row.phone_display || "");
      return digits.includes(q);
    });
  }

  function paintOwnerBlacklistList() {
    if (!els.ownerBlacklist) return;
    const items = filteredBlacklistItems();
    const total = blacklistState.items.length;
    if (els.blacklistFilterMeta) {
      if (!total) {
        els.blacklistFilterMeta.classList.add("hidden");
        els.blacklistFilterMeta.textContent = "";
      } else {
        els.blacklistFilterMeta.classList.remove("hidden");
        els.blacklistFilterMeta.textContent = `Показано ${items.length} з ${total}`;
      }
    }
    if (!total) {
      els.ownerBlacklist.innerHTML = `<div class="empty">Чорний список порожній</div>`;
      return;
    }
    if (!items.length) {
      els.ownerBlacklist.innerHTML = `<div class="empty">Нічого не знайдено за номером</div>`;
      return;
    }
    els.ownerBlacklist.innerHTML = items
      .map((row) => {
        const phone = row.phone_display || row.phone_digits || "";
        const digits = row.phone_digits || blacklistPhoneDigits(phone);
        const buyout = row.buyout || {};
        const received = Number(buyout.received || 0);
        const lost = Number(buyout.lost || 0);
        const completed = Number(buyout.completed || 0);
        const statsLine =
          completed > 0
            ? `Забрано ${received} з ${completed} · незаборів ${lost}`
            : row.orders_total
              ? `Замовлень: ${row.orders_total} (ще немає завершених)`
              : "Немає завершених замовлень";
        return `
          <article class="owner-card blacklist-card is-collapsed" data-blacklist-phone="${escapeHtml(
            digits
          )}" data-blacklist-id="${escapeHtml(String(row.id))}">
            <button type="button" class="owner-card-toggle" aria-expanded="false">
              <div class="owner-card-head">
                <div class="owner-card-title-row">
                  <div class="owner-card-title">${escapeHtml(phone)}</div>
                  ${buyoutBadgeHtml(buyout)}
                </div>
                ${
                  row.note
                    ? `<div class="meta">${escapeHtml(row.note)}</div>`
                    : ""
                }
                <div class="meta-soft">${escapeHtml(statsLine)}</div>
                <div class="meta-soft">${escapeHtml(row.created_at || "")}</div>
              </div>
              <span class="owner-card-chevron" aria-hidden="true"></span>
            </button>
            <div class="blacklist-card-actions">
              <button type="button" class="btn secondary" data-blacklist-del="${escapeHtml(
                String(row.id)
              )}">Видалити</button>
            </div>
            <div class="blacklist-client-panel" data-blacklist-detail hidden></div>
          </article>`;
      })
      .join("");
  }

  function blacklistOutcomeHtml(outcome) {
    if (outcome === "received") {
      return `<span class="blacklist-outcome is-received">забрав</span>`;
    }
    if (outcome === "lost") {
      return `<span class="blacklist-outcome is-lost">не забрав / відмова</span>`;
    }
    return `<span class="blacklist-outcome is-open">в процесі</span>`;
  }

  function renderBlacklistClientPanel(box, profile) {
    const buyout = profile.buyout || {};
    const orders = profile.orders || [];
    const received = Number(buyout.received || 0);
    const lost = Number(buyout.lost || 0);
    const completed = Number(buyout.completed || 0);
    const totalOrders = Number(profile.orders_total || orders.length || 0);
    const pct =
      buyout.percent != null && Number.isFinite(Number(buyout.percent))
        ? `${buyout.percent}%`
        : "—";
    const statsHtml = `
      <div class="blacklist-stats">
        <div>Усього замовлень: <b>${escapeHtml(String(totalOrders))}</b></div>
        <div>Забрав: <b>${escapeHtml(String(received))}</b> · не забрав/відмова: <b>${escapeHtml(
          String(lost)
        )}</b></div>
        <div>Завершених: <b>${escapeHtml(String(completed))}</b> · % забору: <b>${escapeHtml(
          pct
        )}</b></div>
        ${buyoutBadgeHtml(buyout)}
      </div>`;
    const ordersHtml = orders.length
      ? orders
          .map(
            (o) => `
        <div class="blacklist-order">
          <div class="meta"><b>${escapeHtml(o.order_number || "—")}</b> · ${blacklistOutcomeHtml(
              o.outcome
            )}</div>
          <div class="meta">${escapeHtml(o.cart_summary || "—")}</div>
          <div class="meta-soft">Дроппер: ${escapeHtml(o.dropper_name || "—")}${
              o.client_name ? ` · ${escapeHtml(o.client_name)}` : ""
            }</div>
          <div class="meta-soft">${escapeHtml(o.created_at || "")}${
              o.ttn_number ? ` · ТТН ${escapeHtml(o.ttn_number)}` : ""
            }${
              o.total != null
                ? ` · ${escapeHtml(formatMoney(o.total))}`
                : ""
            }</div>
        </div>`
          )
          .join("")
      : `<div class="empty">Замовлень по цьому номеру не знайдено</div>`;
    box.innerHTML = `${statsHtml}${ordersHtml}`;
    box.hidden = false;
  }

  async function loadBlacklistClientDetail(card) {
    const phone = card.getAttribute("data-blacklist-phone") || "";
    if (!phone) return;
    let box = card.querySelector("[data-blacklist-detail]");
    if (!box) {
      box = document.createElement("div");
      box.className = "blacklist-client-panel";
      box.setAttribute("data-blacklist-detail", "1");
      card.appendChild(box);
    }
    if (box.dataset.loaded === "1") {
      box.hidden = false;
      return;
    }
    box.hidden = false;
    box.innerHTML = `<div class="ac-loading">Завантаження клієнта...</div>`;
    try {
      const params = new URLSearchParams(ownerAuthParams());
      params.set("phone", phone);
      params.set("limit", "100");
      const response = await fetch(`/api/owner/blacklist/client?${params.toString()}`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
      }
      renderBlacklistClientPanel(box, data);
      box.dataset.loaded = "1";
    } catch (error) {
      box.innerHTML = `<div class="form-error">${escapeHtml(error.message || "Помилка")}</div>`;
    }
  }

  function updateBroadcastSelectedCount() {
    if (!els.ownerBroadcastCount || !els.ownerDroppers) return;
    const n = els.ownerDroppers.querySelectorAll(
      '[data-broadcast-pick]:checked'
    ).length;
    els.ownerBroadcastCount.textContent = `Обрано: ${n}`;
  }

  function setBroadcastMode(on) {
    const enabled = Boolean(on);
    if (els.ownerBroadcastPanel) {
      els.ownerBroadcastPanel.classList.toggle("hidden", !enabled);
    }
    if (els.ownerBroadcastOpen) {
      els.ownerBroadcastOpen.classList.toggle("is-active", enabled);
    }
    if (els.ownerDroppers) {
      els.ownerDroppers.classList.toggle("owner-droppers-broadcast", enabled);
    }
    if (!enabled && els.ownerDroppers) {
      els.ownerDroppers
        .querySelectorAll("[data-broadcast-pick]")
        .forEach((box) => {
          box.checked = false;
        });
    }
    if (els.ownerBroadcastError) {
      els.ownerBroadcastError.classList.add("hidden");
      els.ownerBroadcastError.textContent = "";
    }
    updateBroadcastSelectedCount();
  }

  function setBroadcastPicks(checked) {
    if (!els.ownerDroppers) return;
    els.ownerDroppers.querySelectorAll("[data-broadcast-pick]").forEach((box) => {
      box.checked = Boolean(checked);
    });
    updateBroadcastSelectedCount();
  }

  async function saveDropperSetting(chatId, patch) {
    const response = await fetch(
      `/api/owner/droppers/${encodeURIComponent(chatId)}/settings`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ownerAuthBody(patch)),
      }
    );
    const data = await response.json();
    if (!response.ok) {
      throw new Error(typeof data.detail === "string" ? data.detail : "Помилка збереження");
    }
    return data.dropper;
  }

  let ownerDroppersCache = [];

  function renderReferralLinkedList(refs) {
    const list = Array.isArray(refs) ? refs : [];
    if (!list.length) {
      return `<div class="meta-soft">Поки нікого не привʼязано</div>`;
    }
    return list
      .map(
        (r) => `
      <div class="referral-linked-item" data-referred-chat="${escapeHtml(r.chat_id || "")}">
        <div>
          <div class="meta"><b>${escapeHtml(r.company_name || "")}</b></div>
          <div class="meta-soft">${escapeHtml(r.phone || "")} · ${escapeHtml(r.chat_id || "")}</div>
        </div>
        <button type="button" class="btn secondary" data-referral-unlink title="Відвʼязати">✕</button>
      </div>`
      )
      .join("");
  }

  function paintReferralSearchResults(card, query) {
    const box = card.querySelector("[data-referral-search-results]");
    if (!box) return;
    const referrerChat = card.getAttribute("data-dropper-chat") || "";
    const linked = new Set(
      Array.from(card.querySelectorAll("[data-referred-chat]")).map((el) =>
        el.getAttribute("data-referred-chat")
      )
    );
    const q = String(query || "").trim().toLowerCase();
    if (q.length < 1) {
      box.classList.add("hidden");
      box.innerHTML = "";
      return;
    }
    const hits = (ownerDroppersCache || [])
      .filter((d) => {
        if (!d || d.chat_id === referrerChat) return false;
        if (linked.has(d.chat_id)) return false;
        const hay = `${d.company_name || ""} ${d.contact_name || ""} ${d.phone || ""} ${
          d.chat_id || ""
        }`.toLowerCase();
        return hay.includes(q);
      })
      .slice(0, 8);
    if (!hits.length) {
      box.classList.remove("hidden");
      box.innerHTML = `<div class="meta-soft">Нічого не знайдено</div>`;
      return;
    }
    box.classList.remove("hidden");
    box.innerHTML = hits
      .map(
        (d) => `
      <button type="button" class="referral-search-hit" data-referral-pick="${escapeHtml(
        d.chat_id || ""
      )}">
        <b>${escapeHtml(d.company_name || "")}</b>
        <span class="meta-soft">${escapeHtml(d.phone || "")} · ${escapeHtml(d.chat_id || "")}</span>
      </button>`
      )
      .join("");
  }

  async function renderOwnerCabinet() {
    els.ownerDroppers.innerHTML = `<div class="ac-loading">Завантаження дропперів...</div>`;
    els.ownerStaff.innerHTML = `<div class="ac-loading">Завантаження...</div>`;
    try {
      const auth = ownerAuthParams();
      const [droppersRes, staffRes] = await Promise.all([
        fetch(`/api/owner/droppers?${auth}`),
        fetch(`/api/owner/staff?${auth}`),
      ]);
      const droppersData = await droppersRes.json();
      const staffData = await staffRes.json();
      if (!droppersRes.ok) throw new Error(droppersData.detail || "Помилка дропперів");
      if (!staffRes.ok) throw new Error(staffData.detail || "Помилка співробітників");

      const droppers = droppersData.items || [];
      ownerDroppersCache = droppers;
      els.ownerDroppers.innerHTML = droppers.length
        ? droppers
            .map(
              (d) => `
          <article class="owner-card is-collapsed" data-dropper-chat="${escapeHtml(d.chat_id)}">
            <label class="owner-card-pick">
              <input type="checkbox" data-broadcast-pick value="${escapeHtml(d.chat_id)}" />
              Обрати для розсилки
            </label>
            <button type="button" class="owner-card-toggle" aria-expanded="false">
              <div class="owner-card-head">
                <h3 class="owner-card-title">${escapeHtml(d.company_name)}</h3>
                <p class="meta">${escapeHtml(d.contact_name)} · ${escapeHtml(d.phone)}</p>
                <p class="meta">chat_id: <b>${escapeHtml(d.chat_id)}</b></p>
                <p class="meta">
                  ${
                    d.referral_program_enabled && d.referral_code
                      ? `Реф. код: <b>${escapeHtml(d.referral_code)}</b> · ${escapeHtml(
                          String(d.referral_percent || 0)
                        )}% · ${escapeHtml(String(d.referral_months || 12))} міс.`
                      : `Реферальна програма: <b>вимкнено</b>`
                  }
                  ${d.referred_by_name ? ` · запрошений: ${escapeHtml(d.referred_by_name)}` : ""}
                  ${d.referrals_count ? ` · привів: ${escapeHtml(String(d.referrals_count))}` : ""}
                </p>
                <p class="meta">Оборот: <b>${escapeHtml(String(Math.round(Number(d.turnover) || 0)))} ₴</b>
                  ${d.credit_holidays_blocked ? ` · <span class="stock-out">канікули: блок</span>` : ""}
                </p>
              </div>
              <span class="owner-card-chevron" aria-hidden="true"></span>
            </button>
            <div class="owner-settings">
              <label class="setting-row">
                <span class="setting-copy">
                  <span class="setting-label">Можливість передавати замовлення наложкою</span>
                  <span class="setting-hint">Оплата при отриманні в формі дроппера</span>
                </span>
                <span class="setting-control">
                  <span class="toggle">
                    <input type="checkbox" data-rule="allow_cod" ${
                      isFlagEnabled(d.allow_cod, true) ? "checked" : ""
                    } />
                    <span class="toggle-ui"></span>
                  </span>
                </span>
              </label>
              <label class="setting-row">
                <span class="setting-copy">
                  <span class="setting-label">Мінус-баланс дозволено</span>
                  <span class="setting-hint">Дозволяє оплату з балансу та борг до ліміту; уже відправлені посилки при отриманні спишуться навіть понад ліміт</span>
                </span>
                <span class="setting-control">
                  <span class="toggle">
                    <input type="checkbox" data-rule="allow_negative_balance" ${
                      d.allow_negative_balance ? "checked" : ""
                    } />
                    <span class="toggle-ui"></span>
                  </span>
                </span>
              </label>
              <label class="setting-row is-nested${
                d.allow_negative_balance ? "" : " is-disabled"
              }" data-negative-limit-row>
                <span class="setting-copy">
                  <span class="setting-label">Ліміт мінусу</span>
                  <span class="setting-hint">Максимальний борг, ₴</span>
                </span>
                <span class="setting-control">
                  <input class="setting-input" type="number" min="0" step="1"
                    data-rule-num="negative_balance_limit"
                    value="${escapeHtml(String(d.negative_balance_limit || 0))}"
                    ${d.allow_negative_balance ? "" : "disabled"} />
                </span>
              </label>
              <label class="setting-row is-nested${
                d.allow_negative_balance ? "" : " is-disabled"
              }" data-credit-holidays-row>
                <span class="setting-copy">
                  <span class="setting-label">Кредитні канікули</span>
                  <span class="setting-hint">Днів до блоку після 85% ліміту боргу (0 = вимкнено)</span>
                </span>
                <span class="setting-control">
                  <input class="setting-input" type="number" min="0" step="1"
                    data-rule-num="credit_holidays_days"
                    value="${escapeHtml(String(d.credit_holidays_days || 0))}"
                    ${d.allow_negative_balance ? "" : "disabled"} />
                </span>
              </label>
              <label class="setting-row">
                <span class="setting-copy">
                  <span class="setting-label">Додаткова знижка</span>
                  <span class="setting-hint">Відсоток від дроп-ціни</span>
                </span>
                <span class="setting-control">
                  <input class="setting-input" type="number" min="0" max="100" step="0.1"
                    data-rule-num="extra_discount_percent"
                    value="${escapeHtml(String(Math.min(100, Number(d.extra_discount_percent) || 0)))}" />
                </span>
              </label>
              <label class="setting-row">
                <span class="setting-copy">
                  <span class="setting-label">Реферальна програма</span>
                  <span class="setting-hint">Код згенерується і збережеться; вимкнення не змінює код</span>
                </span>
                <span class="setting-control">
                  <span class="toggle">
                    <input type="checkbox" data-rule="referral_program_enabled" ${
                      d.referral_program_enabled ? "checked" : ""
                    } />
                    <span class="toggle-ui"></span>
                  </span>
                </span>
              </label>
              <label class="setting-row is-nested${
                d.referral_program_enabled ? "" : " is-disabled"
              }" data-referral-percent-row>
                <span class="setting-copy">
                  <span class="setting-label">Реферальний %</span>
                  <span class="setting-hint">З дроп-ціни приведених${
                    d.referral_code
                      ? ` · код ${escapeHtml(d.referral_code)}`
                      : " · код зʼявиться після увімкнення"
                  }</span>
                </span>
                <span class="setting-control">
                  <input class="setting-input" type="number" min="0" max="100" step="0.1"
                    data-rule-num="referral_percent"
                    value="${escapeHtml(String(Math.min(100, Number(d.referral_percent) || 0)))}"
                    ${d.referral_program_enabled ? "" : "disabled"} />
                </span>
              </label>
              <label class="setting-row is-nested${
                d.referral_program_enabled ? "" : " is-disabled"
              }" data-referral-months-row>
                <span class="setting-copy">
                  <span class="setting-label">Період, місяців</span>
                  <span class="setting-hint">Скільки місяців нараховувати % з продажів приведеного</span>
                </span>
                <span class="setting-control">
                  <input class="setting-input" type="number" min="1" max="120" step="1"
                    data-rule-num="referral_months"
                    value="${escapeHtml(String(Math.max(1, Number(d.referral_months) || 12)))}"
                    ${d.referral_program_enabled ? "" : "disabled"} />
                </span>
              </label>
              <div class="setting-block is-nested${
                d.referral_program_enabled ? "" : " is-disabled"
              }" data-referral-tree-row>
                <span class="setting-label">Привʼязати дропперів</span>
                <span class="setting-hint">Пошук за назвою / телефоном / chat_id — додає в реферальне дерево</span>
                <div class="referral-link-row">
                  <input type="text" class="setting-input" data-referral-search
                    placeholder="Пошук дроппера…" autocomplete="off"
                    ${d.referral_program_enabled ? "" : "disabled"} />
                </div>
                <div class="referral-search-results hidden" data-referral-search-results></div>
                <div class="referral-linked-list" data-referral-linked>
                  ${renderReferralLinkedList(d.referrals || [])}
                </div>
              </div>
              <label class="setting-row">
                <span class="setting-copy">
                  <span class="setting-label">Блокування замовлень</span>
                  <span class="setting-hint">Повне погашення боргу</span>
                </span>
                <span class="setting-control">
                  <span class="toggle">
                    <input type="checkbox" data-rule="orders_disabled" ${
                      d.orders_disabled ? "checked" : ""
                    } />
                    <span class="toggle-ui"></span>
                  </span>
                </span>
              </label>
              <div class="setting-block">
                <span class="setting-label">Коментар</span>
                <span class="setting-hint">Бачать лише власник, адмін і менеджер</span>
                <textarea class="setting-comment" rows="3" data-owner-comment
                  placeholder="Нотатка про дроппера...">${escapeHtml(d.owner_comment || "")}</textarea>
                <button type="button" class="btn secondary block" data-save-comment>Зберегти</button>
              </div>
              <div class="setting-block danger-block">
                <button type="button" class="btn danger block" data-delete-dropper>
                  ✕ Видалити дропшиппера
                </button>
              </div>
            </div>
          </article>`
            )
            .join("")
        : `<div class="empty">Поки немає зареєстрованих дропперів</div>`;

      const staff = staffData.items || [];
      els.ownerStaff.innerHTML = staff.length
        ? staff
            .map(
              (s) => `
          <article class="owner-card">
            <div class="owner-card-title">${escapeHtml(s.full_name || s.telegram_user_id)}</div>
            <div class="meta">${escapeHtml(staffRoleLabel(s.role))} · ${escapeHtml(
                s.username ? `@${String(s.username).replace(/^@/, "")}` : s.telegram_user_id
              )}</div>
          </article>`
            )
            .join("")
        : `<div class="empty">Співробітників ще немає</div>`;
    } catch (error) {
      const msg = `<div class="form-error">${escapeHtml(error.message || "Помилка")}</div>`;
      els.ownerDroppers.innerHTML = msg;
      els.ownerStaff.innerHTML = msg;
    }
  }

  function previewModeLabel(mode) {
    const map = {
      owner: "Власник",
      dropper: "Дроппер",
      admin: "Адмін",
      manager: "Менеджер",
      warehouse: "Кладовщик",
    };
    return map[mode] || mode;
  }

  function syncPreviewBarControls() {
    if (!els.rolePreviewBar) return;
    const isOwner = sessionState.role === "owner";
    els.rolePreviewBar.classList.toggle("hidden", !isOwner);
    if (!isOwner) {
      if (els.previewBanner) els.previewBanner.classList.add("hidden");
      return;
    }
    if (els.previewRoleSelect) els.previewRoleSelect.value = previewState.mode;
    if (els.previewDropperWrap) {
      els.previewDropperWrap.classList.toggle("hidden", previewState.mode !== "dropper");
    }
    if (els.previewDropperSelect && previewState.dropperChatId) {
      els.previewDropperSelect.value = previewState.dropperChatId;
    }
    if (els.previewBackOwner) {
      els.previewBackOwner.classList.toggle("hidden", previewState.mode === "owner");
    }
    if (els.previewBanner) {
      if (previewState.mode === "owner") {
        els.previewBanner.classList.add("hidden");
        els.previewBanner.textContent = "";
      } else {
        let text = `Режим перегляду: ${previewModeLabel(previewState.mode)}`;
        if (previewState.mode === "dropper") {
          const opt = els.previewDropperSelect?.selectedOptions?.[0];
          const name = opt && opt.value ? opt.textContent.trim() : "";
          if (name) text += ` · ${name}`;
          else text += " · оберіть дроппера";
        }
        els.previewBanner.textContent = text;
        els.previewBanner.classList.remove("hidden");
      }
    }
  }

  async function ensurePreviewDroppersLoaded() {
    if (previewState.droppersLoaded || !els.previewDropperSelect) return;
    try {
      const response = await fetch(`/api/owner/droppers?${ownerAuthParams()}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Помилка списку дропперів");
      const items = data.items || [];
      const prev = previewState.dropperChatId;
      els.previewDropperSelect.innerHTML =
        `<option value="">Оберіть дроппера…</option>` +
        items
          .map(
            (d) =>
              `<option value="${escapeHtml(d.chat_id)}">${escapeHtml(
                d.company_name || d.chat_id
              )}</option>`
          )
          .join("");
      if (prev && items.some((d) => String(d.chat_id) === String(prev))) {
        els.previewDropperSelect.value = prev;
        previewState.dropperChatId = prev;
      } else {
        previewState.dropperChatId = "";
      }
      previewState.droppersLoaded = true;
    } catch (error) {
      console.warn("preview droppers", error);
      showToast(error.message || "Не вдалося завантажити дропперів");
    }
  }

  function setTopbarOrderVisible(show) {
    if (els.topbarActions) els.topbarActions.classList.toggle("hidden", !show);
    if (els.cartChip) els.cartChip.classList.toggle("hidden", !show);
    if (els.settingsChip) els.settingsChip.classList.toggle("hidden", !show);
  }

  function resetVisibleViews() {
    els.bootStatus.classList.add("hidden");
    els.registerView.classList.add("hidden");
    els.ownerView.classList.add("hidden");
    els.orderMain.classList.add("hidden");
    els.mainTabs.classList.add("hidden");
    setTopbarOrderVisible(false);
    if (els.balanceView) els.balanceView.classList.add("hidden");
    if (els.dropperSettingsView) els.dropperSettingsView.classList.add("hidden");
    if (els.warehouseView) els.warehouseView.classList.add("hidden");
  }

  function resetOrderUiForPreviewDropper(chatId) {
    const key = String(chatId || "");
    if (previewState.cartForChatId === key) return;
    saveCart([]);
    updateCartIndicators();
    previewState.cartForChatId = key;
    checkoutDraft = null;
    if (els.results) els.results.innerHTML = "";
    if (els.status) els.status.textContent = "";
    if (els.confirmView) els.confirmView.classList.add("hidden");
    if (els.checkoutView) els.checkoutView.classList.add("hidden");
    if (els.catalogView) els.catalogView.classList.remove("hidden");
    if (els.cartView) els.cartView.classList.add("hidden");
    if (els.historyView) els.historyView.classList.add("hidden");
  }

  async function applyPreviewMode() {
    if (sessionState.role !== "owner") {
      syncPreviewBarControls();
      return;
    }
    syncPreviewBarControls();

    if (previewState.mode === "owner") {
      resetOrderUiForPreviewDropper("");
      showMode("owner");
      return;
    }

    resetVisibleViews();

    if (previewState.mode === "dropper") {
      await ensurePreviewDroppersLoaded();
      syncPreviewBarControls();
      if (!previewState.dropperChatId) {
        resetOrderUiForPreviewDropper("");
        els.bootStatus.classList.remove("hidden");
        els.bootStatus.innerHTML =
          `<div class="blocked-box">Оберіть дроппера у списку вище, щоб побачити його форму.</div>`;
        return;
      }
      resetOrderUiForPreviewDropper(previewState.dropperChatId);
      els.orderMain.classList.remove("hidden");
      els.mainTabs.classList.remove("hidden");
      setTopbarOrderVisible(true);
      loadColorOptions();
      await loadDropperSettings(previewState.dropperChatId);
      syncPaymentAndTtn();
      updateCartIndicators();
      switchTab("catalog");
      return;
    }

    resetOrderUiForPreviewDropper("");
    if (previewState.mode === "warehouse") {
      showMode("warehouse");
      return;
    }
    // staff stubs
    els.bootStatus.classList.remove("hidden");
    els.bootStatus.innerHTML = `<div class="blocked-box">Роль «${escapeHtml(
      staffRoleLabel(previewState.mode)
    )}». Кабінет співробітника — наступний етап.</div>`;
  }

  function showMode(mode) {
    resetVisibleViews();

    if (mode === "register") {
      els.registerView.classList.remove("hidden");
      return;
    }
    if (mode === "owner") {
      previewState.mode = "owner";
      if (els.previewRoleSelect) els.previewRoleSelect.value = "owner";
      syncPreviewBarControls();
      els.ownerView.classList.remove("hidden");
      const initial =
        queryParam("view") === "balances" || queryParam("view") === "balance"
          ? "balances"
          : "droppers";
      setOwnerTab(initial);
      renderOwnerCabinet();
      ensurePreviewDroppersLoaded();
      return;
    }
    if (mode === "balance") {
      els.orderMain.classList.remove("hidden");
      els.mainTabs.classList.remove("hidden");
      setTopbarOrderVisible(true);
      loadColorOptions();
      loadDropperSettings().then(() => {
        syncPaymentAndTtn();
        updateCartIndicators();
        switchTab("balance");
      });
      return;
    }
    if (mode === "dropper") {
      els.orderMain.classList.remove("hidden");
      els.mainTabs.classList.remove("hidden");
      setTopbarOrderVisible(true);
      loadColorOptions();
      loadDropperSettings().then(() => {
        syncPaymentAndTtn();
        updateCartIndicators();
      });
      if (queryParam("view") === "balance") {
        switchTab("balance");
      } else if (queryParam("view") === "history") {
        switchTab("history");
      }
      return;
    }
    if (mode === "warehouse") {
      if (els.warehouseView) els.warehouseView.classList.remove("hidden");
      setWarehouseTab(warehouseTabState || "catalog");
      return;
    }
    if (mode === "dropper_blocked") {
      els.bootStatus.classList.remove("hidden");
      const reason = sessionState.block_reason || "";
      const text =
        reason === "credit_holidays"
          ? "Вичерпано кредитні канікули. Передачу замовлень заблоковано, доки борг не буде погашено повністю (баланс ≥ 0)."
          : "Вас заблоковано для повного погашення боргу. Передача замовлень недоступна. Звʼяжіться з власником.";
      els.bootStatus.innerHTML = `<div class="blocked-box">${text}</div>`;
      return;
    }
    els.bootStatus.classList.remove("hidden");
    els.bootStatus.textContent =
      "Немає доступу. Відкрийте Mini App кнопкою з /menu у потрібному чаті Telegram.";
  }

  async function bootstrapSession() {
    const unsafe = tg?.initDataUnsafe || {};
    sessionState.chat_id =
      (unsafe.chat?.id != null ? String(unsafe.chat.id) : "") || queryParam("chat_id");
    sessionState.user_id =
      (unsafe.user?.id != null ? String(unsafe.user.id) : "") || queryParam("user_id");
    sessionState.username = unsafe.user?.username || "";

    try {
      const response = await fetch(
        `/api/session?chat_id=${encodeURIComponent(sessionState.chat_id)}&user_id=${encodeURIComponent(
          sessionState.user_id
        )}&username=${encodeURIComponent(sessionState.username || "")}`
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "session error");
      sessionState.role = data.role || "guest";
      sessionState.need_registration = Boolean(data.need_registration);
      sessionState.block_reason = data.block_reason || "";
      if (data.chat_id) sessionState.chat_id = String(data.chat_id);

      if (sessionState.role === "owner") {
        showMode("owner");
        return;
      }
      if (sessionState.role === "dropper_blocked") {
        showMode("dropper_blocked");
        return;
      }
      if (sessionState.role === "dropper") {
        showMode("dropper");
        return;
      }
      if (sessionState.need_registration) {
        showMode("register");
        return;
      }
      if (sessionState.role === "warehouse") {
        showMode("warehouse");
        return;
      }
      if (sessionState.role === "admin" || sessionState.role === "manager") {
        els.bootStatus.classList.remove("hidden");
        els.bootStatus.textContent = `Роль «${staffRoleLabel(sessionState.role)}». Кабінет співробітника — наступний етап.`;
        return;
      }
      showMode("denied");
    } catch (error) {
      els.bootStatus.classList.remove("hidden");
      els.bootStatus.textContent = error.message || "Помилка завантаження сесії";
    }
  }

  if (els.registerForm) {
    els.registerForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      els.registerError.classList.add("hidden");
      const payload = {
        chat_id: currentTelegramChatId(),
        company_name: document.getElementById("regCompany").value.trim(),
        contact_name: document.getElementById("regContact").value.trim(),
        phone: document.getElementById("regPhone").value.trim(),
        comment: document.getElementById("regComment").value.trim(),
        user_id: currentTelegramUser().user_id,
        username: currentTelegramUser().username,
      };
      try {
        const response = await fetch("/api/droppers/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(
            typeof data.detail === "string" ? data.detail : "Помилка реєстрації"
          );
        }
        showToast("Реєстрацію завершено");
        safeTgAlert("Реєстрацію успішно завершено. Можна відкривати /menu для замовлень.");
        sessionState.role = "dropper";
        sessionState.need_registration = false;
        showMode("dropper");
      } catch (error) {
        els.registerError.textContent = error.message || "Помилка реєстрації";
        els.registerError.classList.remove("hidden");
      }
    });
  }

  if (els.ownerTabs) {
    els.ownerTabs.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-owner-tab]");
      if (!btn) return;
      setOwnerTab(btn.getAttribute("data-owner-tab"));
    });
  }

  function warehouseAuthParams() {
    const p = new URLSearchParams();
    const chat = currentTelegramChatId() || sessionState.chat_id || "";
    const user = currentTelegramUser();
    if (chat) p.set("chat_id", chat);
    if (user.user_id) p.set("user_id", user.user_id);
    if (user.username) p.set("username", user.username);
    return p.toString();
  }

  function setWarehouseTab(name) {
    warehouseTabState = name || "catalog";
    if (els.warehouseTabs) {
      els.warehouseTabs.querySelectorAll("[data-wh-tab]").forEach((btn) => {
        btn.classList.toggle(
          "active",
          btn.getAttribute("data-wh-tab") === warehouseTabState
        );
      });
    }
    const map = {
      catalog: els.warehouseTabCatalog,
      packing: els.warehouseTabPacking,
      shipping: els.warehouseTabShipping,
      salary: els.warehouseTabSalary,
    };
    Object.entries(map).forEach(([key, el]) => {
      if (!el) return;
      el.classList.toggle("hidden", key !== warehouseTabState);
    });
    if (warehouseTabState === "packing") loadWarehouseQueue("packing");
    if (warehouseTabState === "shipping") loadWarehouseQueue("ready_to_ship");
  }

  function renderWarehouseOrderCard(order, { stage }) {
    const cart = order.cart_summary || [];
    const cartHtml = cart.length
      ? cart
          .map(
            (x) =>
              `${escapeHtml(x.code || "")}${
                x.color ? ` · ${escapeHtml(x.color)}` : ""
              } ×${escapeHtml(String(x.qty || 1))}`
          )
          .join("<br/>")
      : "—";
    const pdfBadge = order.has_ttn_pdf
      ? `<span class="meta-soft">PDF ✓</span>`
      : `<span class="meta-soft">PDF немає</span>`;
    const checkHtml =
      stage === "packing"
        ? `<label class="warehouse-order-check">
            <input type="checkbox" data-wh-ready="${escapeHtml(String(order.id))}" />
            Упаковано → на відправлення
          </label>`
        : `<div class="warehouse-order-actions">
            <label class="warehouse-order-check">
              <input type="checkbox" data-wh-print="${escapeHtml(String(order.id))}" />
              Друкувати
            </label>
            <button type="button" class="btn secondary" data-wh-back="${escapeHtml(
              String(order.id)
            )}">← На пакування</button>
          </div>`;
    return `
      <article class="warehouse-order-card" data-order-id="${escapeHtml(String(order.id))}">
        <div class="warehouse-order-head">
          <div>
            <div><b>${escapeHtml(order.order_number || "")}</b> · ТТН ${escapeHtml(
              order.ttn_number || "—"
            )}</div>
            <div class="meta">${escapeHtml(order.recipient_name || "—")} · ${escapeHtml(
              order.own_ttn ? "власна ТТН" : "ТТН власника"
            )} · ${pdfBadge}</div>
          </div>
          ${checkHtml}
        </div>
        <div class="meta">${cartHtml}</div>
      </article>
    `;
  }

  function getSelectedWarehousePrintIds() {
    if (!els.warehouseShippingList) return [];
    return Array.from(
      els.warehouseShippingList.querySelectorAll("[data-wh-print]:checked")
    )
      .map((el) => el.getAttribute("data-wh-print"))
      .filter(Boolean);
  }

  function syncWarehousePrintButton() {
    if (!els.warehousePrintBtn) return;
    const selected = getSelectedWarehousePrintIds();
    els.warehousePrintBtn.disabled = selected.length === 0;
  }

  function setAllWarehousePrintChecks(checked) {
    if (!els.warehouseShippingList) return;
    els.warehouseShippingList
      .querySelectorAll("[data-wh-print]")
      .forEach((el) => {
        el.checked = Boolean(checked);
      });
    syncWarehousePrintButton();
  }

  async function loadWarehouseQueue(stage) {
    const listEl =
      stage === "ready_to_ship" ? els.warehouseShippingList : els.warehousePackingList;
    if (!listEl) return;
    listEl.innerHTML = `<div class="empty">Завантаження…</div>`;
    if (stage === "ready_to_ship") syncWarehousePrintButton();
    try {
      const params = new URLSearchParams(warehouseAuthParams());
      params.set("stage", stage === "ready_to_ship" ? "ready_to_ship" : "packing");
      const response = await fetch(`/api/warehouse/queue?${params}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Помилка черги");
      const items = data.items || [];
      if (!items.length) {
        listEl.innerHTML = `<div class="empty">${
          stage === "ready_to_ship"
            ? "Немає замовлень на відправлення"
            : "Немає замовлень на пакування"
        }</div>`;
        if (stage === "ready_to_ship") syncWarehousePrintButton();
        return;
      }
      listEl.innerHTML = items
        .map((o) =>
          renderWarehouseOrderCard(o, {
            stage: stage === "ready_to_ship" ? "shipping" : "packing",
          })
        )
        .join("");
      if (stage === "ready_to_ship") syncWarehousePrintButton();
    } catch (error) {
      listEl.innerHTML = `<div class="empty">${escapeHtml(
        error.message || "Помилка"
      )}</div>`;
      if (stage === "ready_to_ship") syncWarehousePrintButton();
    }
  }

  if (els.warehouseTabs) {
    els.warehouseTabs.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-wh-tab]");
      if (!btn) return;
      setWarehouseTab(btn.getAttribute("data-wh-tab"));
    });
  }

  if (els.warehouseSearchForm) {
    els.warehouseSearchForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const q = (els.warehouseSearchInput?.value || "").trim();
      if (!q) return;
      if (els.warehouseSearchStatus) els.warehouseSearchStatus.textContent = "Шукаємо…";
      try {
        const response = await fetch(
          `/api/products/search?q=${encodeURIComponent(q)}&limit=80`
        );
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Помилка пошуку");
        const items = data.items || [];
        if (els.warehouseSearchStatus) {
          els.warehouseSearchStatus.textContent = items.length
            ? `Знайдено варіантів: ${items.length}`
            : "Нічого не знайдено";
        }
        if (els.warehouseResults) {
          els.warehouseResults.innerHTML = items.length
            ? renderCatalogCards(items, { showLocation: true, showAdd: false })
            : "";
          bindOrderCardClicks(els.warehouseResults);
        }
      } catch (error) {
        if (els.warehouseSearchStatus) {
          els.warehouseSearchStatus.textContent = error.message || "Помилка";
        }
      }
    });
  }

  if (els.warehousePackingList) {
    els.warehousePackingList.addEventListener("change", async (event) => {
      const check = event.target.closest("[data-wh-ready]");
      if (!check || !check.checked) return;
      const id = check.getAttribute("data-wh-ready");
      try {
        const response = await fetch(
          `/api/warehouse/orders/${encodeURIComponent(id)}/ready?${warehouseAuthParams()}`,
          { method: "POST" }
        );
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Помилка");
        showToast("Переміщено на відправлення");
        loadWarehouseQueue("packing");
      } catch (error) {
        check.checked = false;
        showToast(error.message || "Помилка");
      }
    });
  }

  if (els.warehouseShippingList) {
    els.warehouseShippingList.addEventListener("click", async (event) => {
      const btn = event.target.closest("[data-wh-back]");
      if (!btn) return;
      const id = btn.getAttribute("data-wh-back");
      try {
        const response = await fetch(
          `/api/warehouse/orders/${encodeURIComponent(id)}/packing?${warehouseAuthParams()}`,
          { method: "POST" }
        );
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Помилка");
        showToast("Повернено на пакування");
        loadWarehouseQueue("ready_to_ship");
      } catch (error) {
        showToast(error.message || "Помилка");
      }
    });
    els.warehouseShippingList.addEventListener("change", (event) => {
      if (!event.target.closest("[data-wh-print]")) return;
      syncWarehousePrintButton();
    });
  }

  if (els.warehouseSelectAllBtn) {
    els.warehouseSelectAllBtn.addEventListener("click", () => {
      setAllWarehousePrintChecks(true);
    });
  }
  if (els.warehouseDeselectAllBtn) {
    els.warehouseDeselectAllBtn.addEventListener("click", () => {
      setAllWarehousePrintChecks(false);
    });
  }

  if (els.warehousePrintBtn) {
    syncWarehousePrintButton();
    els.warehousePrintBtn.addEventListener("click", async () => {
      const ids = getSelectedWarehousePrintIds();
      if (!ids.length) {
        showToast("Виберіть хоча б одну накладну");
        return;
      }
      try {
        const params = new URLSearchParams(warehouseAuthParams());
        ids.forEach((id) => params.append("order_id", id));
        const url = `/api/warehouse/print-labels.pdf?${params}`;
        const response = await fetch(url);
        if (!response.ok) {
          let detail = "Не вдалося зібрати PDF";
          try {
            const data = await response.json();
            if (typeof data.detail === "string") detail = data.detail;
          } catch {
            /* ignore */
          }
          throw new Error(detail);
        }
        const blob = await response.blob();
        const objectUrl = URL.createObjectURL(blob);
        window.open(objectUrl, "_blank", "noopener,noreferrer");
        setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
        showToast("PDF відкрито в новій вкладці");
      } catch (error) {
        showToast(error.message || "Помилка друку");
      }
    });
  }

  if (els.historyBuckets) {
    els.historyBuckets.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-history-bucket]");
      if (!btn) return;
      const bucket = btn.getAttribute("data-history-bucket");
      if (!bucket || bucket === historyBucket) return;
      historyBucket = bucket;
      historyPage = 0;
      syncHistoryBucketTabs();
      paintOrdersHistoryList();
    });
  }

  if (els.historyFiltersToggle && els.historyFiltersPanel) {
    els.historyFiltersToggle.addEventListener("click", () => {
      const open = els.historyFiltersPanel.classList.toggle("hidden") === false;
      els.historyFiltersToggle.classList.toggle("active", open);
      els.historyFiltersToggle.textContent = open ? "Сховати фільтри" : "Фільтри";
    });
    els.historyFiltersPanel.addEventListener("input", (event) => {
      if (!event.target.closest("[data-history-order-filters]")) return;
      historyPage = 0;
      paintOrdersHistoryList();
    });
    els.historyFiltersPanel.addEventListener("change", (event) => {
      if (!event.target.closest("[data-history-order-filters]")) return;
      historyPage = 0;
      paintOrdersHistoryList();
    });
  }
  if (els.historyFiltersReset) {
    els.historyFiltersReset.addEventListener("click", () => {
      els.historyFiltersPanel?.querySelectorAll("input").forEach((input) => {
        input.value = "";
      });
      historyPage = 0;
      paintOrdersHistoryList();
    });
  }
  if (els.historyPagePrev) {
    els.historyPagePrev.addEventListener("click", () => {
      historyPage = Math.max(0, historyPage - 1);
      paintOrdersHistoryList();
    });
  }
  if (els.historyPageNext) {
    els.historyPageNext.addEventListener("click", () => {
      historyPage += 1;
      paintOrdersHistoryList();
    });
  }
  if (els.historyExcelExport) {
    els.historyExcelExport.addEventListener("click", async () => {
      const chatId = effectiveDropperChatId();
      const filters = collectOrderFilterValues(els.historyFiltersPanel);
      const params = new URLSearchParams({ chat_id: chatId });
      params.set("status", historyBucket || "all");
      if (filters.dateFrom) params.set("date_from", filters.dateFrom);
      if (filters.dateTo) params.set("date_to", filters.dateTo);
      try {
        await downloadBlobUrl(
          `/api/dropper/orders/export.xlsx?${params.toString()}`,
          "orders.xlsx"
        );
        showToast("Excel завантажено");
      } catch (error) {
        showToast(error.message || "Помилка Excel");
      }
    });
  }
  if (els.balanceFiltersToggle && els.balanceFiltersPanel) {
    els.balanceFiltersToggle.addEventListener("click", () => {
      const open = els.balanceFiltersPanel.classList.toggle("hidden") === false;
      els.balanceFiltersToggle.classList.toggle("active", open);
      els.balanceFiltersToggle.textContent = open ? "Сховати фільтри" : "Фільтри";
    });
  }
  if (els.balanceExcelExport) {
    els.balanceExcelExport.addEventListener("click", async () => {
      const chatId = effectiveDropperChatId();
      const params = new URLSearchParams({ chat_id: chatId });
      const status = els.balanceFilterStatus?.value || "all";
      if (status && status !== "all") params.set("status", status);
      const from = els.balanceFilterDateFrom?.value || "";
      const to = els.balanceFilterDateTo?.value || "";
      if (from) params.set("date_from", from);
      if (to) params.set("date_to", to);
      try {
        await downloadBlobUrl(
          `/api/dropper/balance/export.xlsx?${params.toString()}`,
          "balance.xlsx"
        );
        showToast("Excel завантажено");
      } catch (error) {
        showToast(error.message || "Помилка Excel");
      }
    });
  }

  if (els.ownerReturnsTabs) {
    els.ownerReturnsTabs.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-returns-bucket]");
      if (!btn || !els.ownerReturnsTabs.contains(btn)) return;
      const bucket = btn.getAttribute("data-returns-bucket") || "awaiting_receipt";
      if (bucket === ownerReturnsState.bucket) return;
      ownerReturnsState.bucket = bucket;
      renderOwnerReturns();
    });
  }

  document.addEventListener("click", (event) => {
    const acceptBtn = event.target.closest("[data-owner-return-accept]");
    if (acceptBtn) {
      event.preventDefault();
      const orderId = acceptBtn.getAttribute("data-owner-return-accept");
      if (orderId) acceptOwnerReturn(orderId);
      return;
    }
    const receivedBtn = event.target.closest("[data-owner-return-received]");
    if (receivedBtn) {
      event.preventDefault();
      const orderId = receivedBtn.getAttribute("data-owner-return-received");
      if (orderId) markOwnerReturnReceived(orderId);
    }
  });

  if (els.previewRoleSelect) {
    els.previewRoleSelect.addEventListener("change", async () => {
      if (sessionState.role !== "owner") return;
      const next = els.previewRoleSelect.value || "owner";
      previewState.mode = next;
      if (next === "dropper") {
        await ensurePreviewDroppersLoaded();
        previewState.dropperChatId = els.previewDropperSelect?.value || "";
      }
      await applyPreviewMode();
    });
  }

  if (els.previewDropperSelect) {
    els.previewDropperSelect.addEventListener("change", async () => {
      if (sessionState.role !== "owner") return;
      previewState.dropperChatId = els.previewDropperSelect.value || "";
      previewState.mode = "dropper";
      if (els.previewRoleSelect) els.previewRoleSelect.value = "dropper";
      await applyPreviewMode();
    });
  }

  if (els.previewBackOwner) {
    els.previewBackOwner.addEventListener("click", async () => {
      if (sessionState.role !== "owner") return;
      previewState.mode = "owner";
      if (els.previewRoleSelect) els.previewRoleSelect.value = "owner";
      await applyPreviewMode();
    });
  }

  if (els.npApiKeyAdd) {
    els.npApiKeyAdd.addEventListener("click", () => {
      generalSettingsState.np_api_keys = collectNpApiKeysFromDom();
      generalSettingsState.np_api_keys.push(
        newNpKeyRow({ label: `Кабінет ${generalSettingsState.np_api_keys.length + 1}` })
      );
      renderNpApiKeys();
    });
  }

  if (els.npApiKeysList) {
    els.npApiKeysList.addEventListener("click", (event) => {
      const removeBtn = event.target.closest("[data-np-remove]");
      if (!removeBtn) return;
      const index = Number(removeBtn.getAttribute("data-np-remove"));
      generalSettingsState.np_api_keys = collectNpApiKeysFromDom();
      const row = generalSettingsState.np_api_keys[index];
      const label = (row && row.label) || "цей API-ключ";
      if (
        !window.confirm(
          `Ви точно впевнені, що хочете видалити ключ «${label}»?\nПісля збереження відновити його буде неможливо без повторного введення.`
        )
      ) {
        return;
      }
      generalSettingsState.np_api_keys.splice(index, 1);
      if (!generalSettingsState.np_api_keys.length) {
        generalSettingsState.np_api_keys = [newNpKeyRow({ label: "Кабінет 1" })];
      }
      renderNpApiKeys();
    });
  }

  if (els.paymentRequisiteAdd) {
    els.paymentRequisiteAdd.addEventListener("click", () => {
      generalSettingsState.payment_requisites = collectPaymentRequisitesFromDom();
      const n = generalSettingsState.payment_requisites.length + 1;
      generalSettingsState.payment_requisites.push(
        newPaymentRequisiteRow({ label: `Реквізити ${n}`, kind: "fop" })
      );
      renderPaymentRequisites();
    });
  }

  if (els.paymentRequisitesList) {
    els.paymentRequisitesList.addEventListener("click", (event) => {
      const removeBtn = event.target.closest("[data-req-remove]");
      if (!removeBtn) return;
      const index = Number(removeBtn.getAttribute("data-req-remove"));
      generalSettingsState.payment_requisites = collectPaymentRequisitesFromDom();
      generalSettingsState.payment_requisites.splice(index, 1);
      if (!generalSettingsState.payment_requisites.length) {
        generalSettingsState.payment_requisites = [
          newPaymentRequisiteRow({ label: "ФОП / рахунок 1", kind: "fop" }),
        ];
      }
      renderPaymentRequisites();
    });
    els.paymentRequisitesList.addEventListener("change", (event) => {
      const select = event.target.closest('[data-req-field="kind"]');
      if (!select) return;
      const row = select.closest("[data-req-index]");
      if (!row) return;
      const kind = select.value === "card" ? "card" : "fop";
      row.querySelectorAll("[data-req-show]").forEach((el) => {
        const show = el.getAttribute("data-req-show");
        el.classList.toggle("hidden", show !== kind);
      });
    });
  }

  if (els.generalSettingsForm) {
    els.generalSettingsForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (els.generalSettingsError) {
        els.generalSettingsError.classList.add("hidden");
        els.generalSettingsError.textContent = "";
      }
      if (els.generalSettingsOk) els.generalSettingsOk.classList.add("hidden");
      try {
        const response = await fetch("/api/owner/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(collectGeneralSettingsPayload()),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(typeof data.detail === "string" ? data.detail : "Помилка збереження");
        }
        fillGeneralSettingsForm(data.settings || {}, generalSettingsState.sheet_columns || []);
        activePaymentRequisites = (data.settings?.payment_requisites || []).filter(
          (r) => r.enabled
        );
        renderRequisitesDetails();
        if (els.generalSettingsOk) {
          els.generalSettingsOk.textContent = `Збережено. Основних кабінетів НП: ${
            data.enabled_np_keys_count || 0
          }. Активних реквізитів: ${data.enabled_payment_requisites_count || 0}`;
          els.generalSettingsOk.classList.remove("hidden");
        }
        showToast("Загальні налаштування збережено");
      } catch (error) {
        if (els.generalSettingsError) {
          els.generalSettingsError.textContent = error.message || "Помилка";
          els.generalSettingsError.classList.remove("hidden");
        }
      }
    });
  }

  if (els.senderCity) {
    els.senderCity.addEventListener("input", () => {
      senderNpState.city = null;
      if (els.senderCityRef) els.senderCityRef.value = "";
      if (els.senderSettlementRef) els.senderSettlementRef.value = "";
      senderNpState.warehouse = null;
      if (els.senderWarehouse) els.senderWarehouse.value = "";
      if (els.senderWarehouseRef) els.senderWarehouseRef.value = "";
      if (els.senderWarehouseNumber) els.senderWarehouseNumber.value = "";
      clearTimeout(senderNpState.cityTimer);
      const q = els.senderCity.value.trim();
      if (q.length < 2) {
        hideDropdown(els.senderCityDropdown);
        return;
      }
      senderNpState.cityTimer = setTimeout(() => searchSenderCities(q), 280);
    });
  }

  if (els.senderCityDropdown) {
    els.senderCityDropdown.addEventListener("mousedown", (event) => {
      const btn = event.target.closest("[data-sender-city-index]");
      if (!btn) return;
      event.preventDefault();
      try {
        const items = JSON.parse(els.senderCityDropdown.dataset.items || "[]");
        const item = items[Number(btn.dataset.senderCityIndex)];
        if (!item) return;
        senderNpState.city = item;
        els.senderCity.value = item.label || item.present || "";
        els.senderCityRef.value = item.city_ref || "";
        els.senderSettlementRef.value = item.settlement_ref || "";
        hideDropdown(els.senderCityDropdown);
        senderNpState.warehouse = null;
        if (els.senderWarehouse) els.senderWarehouse.value = "";
        if (els.senderWarehouseRef) els.senderWarehouseRef.value = "";
        if (els.senderWarehouseNumber) els.senderWarehouseNumber.value = "";
      } catch {
        showToast("Не вдалося обрати місто");
      }
    });
  }

  if (els.senderWarehouse) {
    els.senderWarehouse.addEventListener("input", () => {
      senderNpState.warehouse = null;
      if (els.senderWarehouseRef) els.senderWarehouseRef.value = "";
      if (els.senderWarehouseNumber) els.senderWarehouseNumber.value = "";
      clearTimeout(senderNpState.warehouseTimer);
      const q = els.senderWarehouse.value.trim();
      if (!(senderNpState.city?.city_ref || els.senderCityRef?.value)) return;
      senderNpState.warehouseTimer = setTimeout(
        () => searchSenderWarehouses(q),
        q ? 220 : 0
      );
    });
    els.senderWarehouse.addEventListener("focus", () => {
      if (!(senderNpState.city?.city_ref || els.senderCityRef?.value)) return;
      searchSenderWarehouses(els.senderWarehouse.value || "");
    });
  }

  if (els.senderWarehouseDropdown) {
    els.senderWarehouseDropdown.addEventListener("mousedown", (event) => {
      const btn = event.target.closest("[data-sender-wh-index]");
      if (!btn) return;
      event.preventDefault();
      try {
        const items = JSON.parse(els.senderWarehouseDropdown.dataset.items || "[]");
        const item = items[Number(btn.dataset.senderWhIndex)];
        if (!item) return;
        senderNpState.warehouse = item;
        els.senderWarehouse.value = item.label || item.description || "";
        els.senderWarehouseRef.value = item.ref || "";
        els.senderWarehouseNumber.value = item.number || "";
        hideDropdown(els.senderWarehouseDropdown);
      } catch {
        showToast("Не вдалося обрати відділення");
      }
    });
  }

  document.addEventListener("click", (event) => {
    if (els.senderCityDropdown && !event.target.closest('[data-ac="sender-city"]')) {
      hideDropdown(els.senderCityDropdown);
    }
    if (
      els.senderWarehouseDropdown &&
      !event.target.closest('[data-ac="sender-warehouse"]')
    ) {
      hideDropdown(els.senderWarehouseDropdown);
    }
  });

  if (els.staffForm) {
    els.staffForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      els.staffError.classList.add("hidden");
      const payload = {
        ...ownerAuthBody(),
        telegram: document.getElementById("staffUsername").value.trim(),
        full_name: document.getElementById("staffName").value.trim(),
        role: document.getElementById("staffRole").value,
        created_by_user_id: currentTelegramUser().user_id,
      };
      try {
        const response = await fetch("/api/owner/staff", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
        }
        showToast("Співробітника додано");
        els.staffForm.reset();
        renderOwnerCabinet();
      } catch (error) {
        els.staffError.textContent = error.message || "Помилка";
        els.staffError.classList.remove("hidden");
      }
    });
  }

  if (els.blacklistForm) {
    els.blacklistForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (els.blacklistError) els.blacklistError.classList.add("hidden");
      const phone = (els.blacklistPhone?.value || "").trim();
      const note = (els.blacklistNote?.value || "").trim();
      try {
        const response = await fetch("/api/owner/blacklist", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(ownerAuthBody({ phone, note })),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
        }
        showToast("Номер додано до чорного списку");
        els.blacklistForm.reset();
        renderOwnerBlacklist();
      } catch (error) {
        if (els.blacklistError) {
          els.blacklistError.textContent = error.message || "Помилка";
          els.blacklistError.classList.remove("hidden");
        } else {
          showToast(error.message || "Помилка");
        }
      }
    });
  }

  if (els.blacklistSearch) {
    els.blacklistSearch.addEventListener("input", () => {
      blacklistState.search = (els.blacklistSearch.value || "").trim();
      if (blacklistState.items.length || els.ownerBlacklist) {
        paintOwnerBlacklistList();
      }
    });
  }

  if (els.ownerBlacklist) {
    els.ownerBlacklist.addEventListener("click", async (event) => {
      const delBtn = event.target.closest("[data-blacklist-del]");
      if (delBtn && els.ownerBlacklist.contains(delBtn)) {
        const id = delBtn.getAttribute("data-blacklist-del");
        if (!id) return;
        try {
          const response = await fetch(
            `/api/owner/blacklist/${encodeURIComponent(id)}?${ownerAuthParams()}`,
            { method: "DELETE" }
          );
          const data = await response.json().catch(() => ({}));
          if (!response.ok) {
            throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
          }
          showToast("Номер видалено");
          renderOwnerBlacklist();
        } catch (error) {
          showToast(error.message || "Помилка");
        }
        return;
      }

      const toggle = event.target.closest(".owner-card-toggle");
      if (!toggle || !els.ownerBlacklist.contains(toggle)) return;
      const card = toggle.closest(".blacklist-card");
      if (!card) return;
      const collapsed = card.classList.toggle("is-collapsed");
      toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      if (!collapsed) {
        loadBlacklistClientDetail(card);
      }
    });
  }

  if (els.ownerBalances) {
    els.ownerBalances.addEventListener("click", (event) => {
      const toggle = event.target.closest(".owner-card-toggle");
      if (!toggle || !els.ownerBalances.contains(toggle)) return;
      const card = toggle.closest(".owner-card");
      if (!card) return;
      const collapsed = card.classList.toggle("is-collapsed");
      toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      if (!collapsed) {
        loadOwnerDropperOrders(card);
      }
    });
  }

  if (els.ownerBroadcastOpen) {
    els.ownerBroadcastOpen.addEventListener("click", () => {
      const opening = els.ownerBroadcastPanel?.classList.contains("hidden");
      setBroadcastMode(opening);
      if (opening && els.ownerBroadcastText) {
        els.ownerBroadcastText.focus();
      }
    });
  }
  if (els.ownerBroadcastCancel) {
    els.ownerBroadcastCancel.addEventListener("click", () => {
      if (els.ownerBroadcastText) els.ownerBroadcastText.value = "";
      setBroadcastMode(false);
    });
  }
  if (els.ownerBroadcastSelectAll) {
    els.ownerBroadcastSelectAll.addEventListener("click", () => setBroadcastPicks(true));
  }
  if (els.ownerBroadcastClearAll) {
    els.ownerBroadcastClearAll.addEventListener("click", () => setBroadcastPicks(false));
  }
  if (els.ownerBroadcastSend) {
    els.ownerBroadcastSend.addEventListener("click", async () => {
      if (els.ownerBroadcastError) {
        els.ownerBroadcastError.classList.add("hidden");
        els.ownerBroadcastError.textContent = "";
      }
      const message = (els.ownerBroadcastText?.value || "").trim();
      const chatIds = [
        ...(els.ownerDroppers?.querySelectorAll("[data-broadcast-pick]:checked") || []),
      ].map((box) => box.value);
      if (!message) {
        if (els.ownerBroadcastError) {
          els.ownerBroadcastError.textContent = "Введіть текст повідомлення";
          els.ownerBroadcastError.classList.remove("hidden");
        }
        return;
      }
      if (!chatIds.length) {
        if (els.ownerBroadcastError) {
          els.ownerBroadcastError.textContent = "Оберіть хоча б одного дроппера";
          els.ownerBroadcastError.classList.remove("hidden");
        }
        return;
      }
      els.ownerBroadcastSend.disabled = true;
      try {
        const response = await fetch("/api/owner/droppers/broadcast", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            ownerAuthBody({
              message,
              chat_ids: chatIds,
            })
          ),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
        }
        const sent = Number(data.sent || 0);
        const failed = Number(data.failed || 0);
        showToast(
          failed
            ? `Надіслано: ${sent}, помилок: ${failed}`
            : `Повідомлення надіслано: ${sent}`
        );
        if (els.ownerBroadcastText) els.ownerBroadcastText.value = "";
        setBroadcastMode(false);
      } catch (error) {
        if (els.ownerBroadcastError) {
          els.ownerBroadcastError.textContent = error.message || "Помилка";
          els.ownerBroadcastError.classList.remove("hidden");
        } else {
          showToast(error.message || "Помилка");
        }
      } finally {
        els.ownerBroadcastSend.disabled = false;
      }
    });
  }

  if (els.ownerDroppers) {
    const persistRule = async (card, patch, rollback) => {
      const chatId = card.getAttribute("data-dropper-chat");
      try {
        await saveDropperSetting(chatId, patch);
        showToast("Налаштування збережено");
      } catch (error) {
        showToast(error.message || "Не вдалося зберегти");
        if (typeof rollback === "function") rollback();
      }
    };

    els.ownerDroppers.addEventListener("click", async (event) => {
      if (event.target.closest("[data-broadcast-pick], .owner-card-pick")) {
        return;
      }
      const toggle = event.target.closest(".owner-card-toggle");
      if (toggle && els.ownerDroppers.contains(toggle)) {
        const card = toggle.closest(".owner-card");
        if (!card) return;
        const collapsed = card.classList.toggle("is-collapsed");
        toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
        return;
      }

      const saveBtn = event.target.closest("[data-save-comment]");
      if (saveBtn && els.ownerDroppers.contains(saveBtn)) {
        const card = saveBtn.closest("[data-dropper-chat]");
        if (!card) return;
        const area = card.querySelector("[data-owner-comment]");
        const text = area ? area.value : "";
        saveBtn.disabled = true;
        try {
          await saveDropperSetting(card.getAttribute("data-dropper-chat"), {
            owner_comment: text,
          });
          showToast("Коментар збережено");
        } catch (error) {
          showToast(error.message || "Не вдалося зберегти");
        } finally {
          saveBtn.disabled = false;
        }
        return;
      }

      const delBtn = event.target.closest("[data-delete-dropper]");
      if (delBtn && els.ownerDroppers.contains(delBtn)) {
        const card = delBtn.closest("[data-dropper-chat]");
        if (!card) return;
        const chatId = card.getAttribute("data-dropper-chat");
        const title =
          card.querySelector(".owner-card-title")?.textContent?.trim() || chatId;
        if (
          !window.confirm(
            `Видалити дроппера «${title}»?\nПісля цього йому потрібна нова реєстрація.`
          )
        ) {
          return;
        }
        delBtn.disabled = true;
        try {
          const response = await fetch(
            `/api/owner/droppers/${encodeURIComponent(chatId)}?${ownerAuthParams()}`,
            { method: "DELETE" }
          );
          const data = await response.json();
          if (!response.ok) {
            throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
          }
          showToast("Дроппера видалено");
          previewState.droppersLoaded = false;
          if (previewState.dropperChatId === chatId) {
            previewState.dropperChatId = "";
          }
          renderOwnerCabinet();
          ensurePreviewDroppersLoaded();
        } catch (error) {
          showToast(error.message || "Не вдалося видалити");
          delBtn.disabled = false;
        }
        return;
      }

      const pickBtn = event.target.closest("[data-referral-pick]");
      if (pickBtn && els.ownerDroppers.contains(pickBtn)) {
        const card = pickBtn.closest("[data-dropper-chat]");
        const referrerChat = card?.getAttribute("data-dropper-chat");
        const referredChat = pickBtn.getAttribute("data-referral-pick");
        if (!referrerChat || !referredChat) return;
        try {
          const response = await fetch(
            `/api/owner/droppers/${encodeURIComponent(referrerChat)}/referrals`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                ...ownerAuthBody(),
                referred_chat_id: referredChat,
              }),
            }
          );
          const data = await response.json();
          if (!response.ok) {
            throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
          }
          const list = card.querySelector("[data-referral-linked]");
          if (list) list.innerHTML = renderReferralLinkedList(data.referrals || []);
          const search = card.querySelector("[data-referral-search]");
          if (search) search.value = "";
          const results = card.querySelector("[data-referral-search-results]");
          if (results) {
            results.classList.add("hidden");
            results.innerHTML = "";
          }
          showToast("Дроппера привʼязано");
          const cached = ownerDroppersCache.find((x) => x.chat_id === referrerChat);
          if (cached) cached.referrals = data.referrals || [];
        } catch (error) {
          showToast(error.message || "Не вдалося привʼязати");
        }
        return;
      }

      const unlinkBtn = event.target.closest("[data-referral-unlink]");
      if (unlinkBtn && els.ownerDroppers.contains(unlinkBtn)) {
        const card = unlinkBtn.closest("[data-dropper-chat]");
        const item = unlinkBtn.closest("[data-referred-chat]");
        const referrerChat = card?.getAttribute("data-dropper-chat");
        const referredChat = item?.getAttribute("data-referred-chat");
        if (!referrerChat || !referredChat) return;
        try {
          const response = await fetch(
            `/api/owner/droppers/${encodeURIComponent(
              referrerChat
            )}/referrals/${encodeURIComponent(referredChat)}?${ownerAuthParams()}`,
            { method: "DELETE" }
          );
          const data = await response.json();
          if (!response.ok) {
            throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
          }
          const list = card.querySelector("[data-referral-linked]");
          if (list) list.innerHTML = renderReferralLinkedList(data.referrals || []);
          showToast("Привʼязку знято");
          const cached = ownerDroppersCache.find((x) => x.chat_id === referrerChat);
          if (cached) cached.referrals = data.referrals || [];
        } catch (error) {
          showToast(error.message || "Не вдалося відвʼязати");
        }
      }
    });

    els.ownerDroppers.addEventListener("input", (event) => {
      const search = event.target.closest("[data-referral-search]");
      if (!search || !els.ownerDroppers.contains(search)) return;
      const card = search.closest("[data-dropper-chat]");
      if (!card) return;
      paintReferralSearchResults(card, search.value);
    });

    els.ownerDroppers.addEventListener("change", async (event) => {
      if (event.target.matches("[data-broadcast-pick]")) {
        updateBroadcastSelectedCount();
        return;
      }
      const card = event.target.closest("[data-dropper-chat]");
      if (!card) return;
      const check = event.target.closest("[data-rule]");
      const num = event.target.closest("[data-rule-num]");
      if (check) {
        const key = check.getAttribute("data-rule");
        const prev = !check.checked;
        if (key === "allow_negative_balance") {
          const limitRow = card.querySelector("[data-negative-limit-row]");
          const limitInput = card.querySelector('[data-rule-num="negative_balance_limit"]');
          const holidaysRow = card.querySelector("[data-credit-holidays-row]");
          const holidaysInput = card.querySelector('[data-rule-num="credit_holidays_days"]');
          if (limitRow && limitInput) {
            const enabled = Boolean(check.checked);
            limitRow.classList.toggle("is-disabled", !enabled);
            limitInput.disabled = !enabled;
          }
          if (holidaysRow && holidaysInput) {
            const enabled = Boolean(check.checked);
            holidaysRow.classList.toggle("is-disabled", !enabled);
            holidaysInput.disabled = !enabled;
          }
        }
        if (key === "referral_program_enabled") {
          const percentRow = card.querySelector("[data-referral-percent-row]");
          const percentInput = card.querySelector('[data-rule-num="referral_percent"]');
          const monthsRow = card.querySelector("[data-referral-months-row]");
          const monthsInput = card.querySelector('[data-rule-num="referral_months"]');
          const treeRow = card.querySelector("[data-referral-tree-row]");
          const searchInput = card.querySelector("[data-referral-search]");
          const enabled = Boolean(check.checked);
          if (percentRow && percentInput) {
            percentRow.classList.toggle("is-disabled", !enabled);
            percentInput.disabled = !enabled;
          }
          if (monthsRow && monthsInput) {
            monthsRow.classList.toggle("is-disabled", !enabled);
            monthsInput.disabled = !enabled;
          }
          if (treeRow) treeRow.classList.toggle("is-disabled", !enabled);
          if (searchInput) searchInput.disabled = !enabled;
        }
        await persistRule(card, { [key]: Boolean(check.checked) }, () => {
          check.checked = prev;
          if (key === "allow_negative_balance") {
            const limitRow = card.querySelector("[data-negative-limit-row]");
            const limitInput = card.querySelector('[data-rule-num="negative_balance_limit"]');
            const holidaysRow = card.querySelector("[data-credit-holidays-row]");
            const holidaysInput = card.querySelector('[data-rule-num="credit_holidays_days"]');
            if (limitRow && limitInput) {
              const enabled = Boolean(check.checked);
              limitRow.classList.toggle("is-disabled", !enabled);
              limitInput.disabled = !enabled;
            }
            if (holidaysRow && holidaysInput) {
              const enabled = Boolean(check.checked);
              holidaysRow.classList.toggle("is-disabled", !enabled);
              holidaysInput.disabled = !enabled;
            }
          }
          if (key === "referral_program_enabled") {
            const percentRow = card.querySelector("[data-referral-percent-row]");
            const percentInput = card.querySelector('[data-rule-num="referral_percent"]');
            const monthsRow = card.querySelector("[data-referral-months-row]");
            const monthsInput = card.querySelector('[data-rule-num="referral_months"]');
            const treeRow = card.querySelector("[data-referral-tree-row]");
            const searchInput = card.querySelector("[data-referral-search]");
            const enabled = Boolean(check.checked);
            if (percentRow && percentInput) {
              percentRow.classList.toggle("is-disabled", !enabled);
              percentInput.disabled = !enabled;
            }
            if (monthsRow && monthsInput) {
              monthsRow.classList.toggle("is-disabled", !enabled);
              monthsInput.disabled = !enabled;
            }
            if (treeRow) treeRow.classList.toggle("is-disabled", !enabled);
            if (searchInput) searchInput.disabled = !enabled;
          }
        });
        if (key === "referral_program_enabled") {
          renderOwnerCabinet();
        }
        return;
      }
      if (num) {
        if (num.disabled) return;
        const key = num.getAttribute("data-rule-num");
        let value = Number(num.value);
        if (!Number.isFinite(value) || value < 0) value = 0;
        if (
          (key === "extra_discount_percent" || key === "referral_percent") &&
          value > 100
        ) {
          value = 100;
        }
        if (key === "referral_months") {
          value = Math.max(1, Math.min(120, Math.round(value) || 12));
        }
        num.value = String(value);
        const prev = num.defaultValue;
        num.defaultValue = String(value);
        await persistRule(card, { [key]: value }, () => {
          num.value = prev;
          num.defaultValue = prev;
        });
      }
    });
  }

  updateCartIndicators();
  bootstrapSession();
})();
