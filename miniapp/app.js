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
    ownerTabSettings: document.getElementById("ownerTabSettings"),
    ownerTabOrder: document.getElementById("ownerTabOrder"),
    ownerTabBlacklist: document.getElementById("ownerTabBlacklist"),
    ownerBlacklist: document.getElementById("ownerBlacklist"),
    blacklistForm: document.getElementById("blacklistForm"),
    blacklistPhone: document.getElementById("blacklistPhone"),
    blacklistNote: document.getElementById("blacklistNote"),
    blacklistError: document.getElementById("blacklistError"),
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
    balanceReferralTotal: document.getElementById("balanceReferralTotal"),
    balanceStats: document.getElementById("balanceStats"),
    balanceLedger: document.getElementById("balanceLedger"),
    balanceHint: document.getElementById("balanceHint"),
    dropperSettingsView: document.getElementById("dropperSettingsView"),
    notifyShippingEvents: document.getElementById("notifyShippingEvents"),
    dropperSettingsStatus: document.getElementById("dropperSettingsStatus"),
    staffForm: document.getElementById("staffForm"),
    staffError: document.getElementById("staffError"),
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
    paymentReceipt: document.getElementById("paymentReceipt"),
    receiptField: document.getElementById("receiptField"),
    requisitesIntro: document.getElementById("requisitesIntro"),
    ttnPdfField: document.getElementById("ttnPdfField"),
    ttnPdf: document.getElementById("ttnPdf"),
    ttnPdfName: document.getElementById("ttnPdfName"),
    paymentReceiptName: document.getElementById("paymentReceiptName"),
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
    require_full_payment: false,
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

  function showToast(text) {
    const node = document.createElement("div");
    node.className = "toast";
    node.textContent = text;
    document.body.appendChild(node);
    setTimeout(() => node.remove(), 2200);
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
    document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
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
    return (
      els.checkoutForm.querySelector('input[name="paymentMethod"]:checked')?.value ||
      "cod"
    );
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
      dropperSettings.require_full_payment = Boolean(data.require_full_payment);
      dropperSettings.allow_cod = data.allow_cod !== false;
      dropperSettings.allow_balance_payment = Boolean(data.allow_balance_payment);
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
      dropperSettings.require_full_payment = false;
      dropperSettings.allow_cod = true;
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
    if (dropperSettings.require_full_payment) {
      els.requisitesIntro.innerHTML =
        `Виконайте оплату в розмірі <strong id="payAmountLabel">${amount}</strong> за реквізитами ` +
        `та завантажте фото/скрін квитанції про оплату.`;
    } else {
      els.requisitesIntro.innerHTML =
        `Виконайте оплату в розмірі <strong id="payAmountLabel">${amount}</strong> за реквізитами.`;
    }
    // payAmountLabel був перезаписаний innerHTML — оновимо посилання
    els.payAmountLabel = document.getElementById("payAmountLabel");
  }

  function balanceSpendRoom() {
    if (!dropperSettings.allow_balance_payment) return 0;
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
    const allowCod = dropperSettings.allow_cod !== false;
    const allowBalance = Boolean(dropperSettings.allow_balance_payment);

    // Без наложки — лише власна ТТН (тумблер не потрібен)
    if (!allowCod && els.ownTtn && !els.ownTtn.checked) {
      els.ownTtn.checked = true;
    }
    if (els.ownTtnToggleRow) {
      els.ownTtnToggleRow.classList.toggle("hidden", !allowCod);
    }

    const ownTtn = Boolean(els.ownTtn?.checked);
    syncOwnTtnCarrierUi();

    // При власній ТТН або без дозволу наложки — COD ховаємо
    const hideCod = ownTtn || !allowCod;
    els.codPaymentCard.classList.toggle("hidden", hideCod);
    els.codPaymentHint.classList.toggle("hidden", hideCod);
    if (els.balancePaymentCard) {
      els.balancePaymentCard.classList.toggle("hidden", !allowBalance);
    }

    let payment = selectedPaymentMethod();
    if (hideCod && payment === "cod") {
      const fallback = allowBalance
        ? els.checkoutForm.querySelector('input[name="paymentMethod"][value="balance"]')
        : els.checkoutForm.querySelector('input[name="paymentMethod"][value="requisites"]');
      if (fallback) fallback.checked = true;
      payment = selectedPaymentMethod();
    }
    if (!allowBalance && payment === "balance") {
      const req = els.checkoutForm.querySelector('input[name="paymentMethod"][value="requisites"]');
      if (req) req.checked = true;
      payment = selectedPaymentMethod();
    }

    const showRequisites = payment === "requisites";
    const showBalance = payment === "balance";
    const showPrepay = !ownTtn && allowCod && payment === "cod";
    const showReceipt = showRequisites && dropperSettings.require_full_payment;

    els.prepayBlock.classList.toggle("hidden", !showPrepay);
    els.requisitesBlock.classList.toggle("hidden", !showRequisites);
    els.receiptField.classList.toggle("hidden", !showReceipt);
    if (els.balancePayHint) els.balancePayHint.classList.toggle("hidden", !showBalance);

    const total = cartMoneyTotal();
    updatePrepayUi(total);
    updateRequisitesIntro(total);
    if (els.balancePayHint && showBalance) {
      const room = balanceSpendRoom();
      els.balancePayHint.textContent =
        `Суму «Дроп ціна» (${formatMoneyAmount(total)} грн) буде списано з балансу. ` +
        `Доступно з урахуванням ліміту мінусу: ${formatMoneyAmount(room)} грн.`;
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

  function renderResults(items) {
    closePhotoZoom();
    if (!items.length) {
      els.results.innerHTML = "";
      els.status.textContent = "Нічого не знайдено за цим кодом";
      return;
    }

    const cart = loadCart();
    els.status.textContent = `Знайдено варіантів: ${items.length}`;
    els.results.innerHTML = items
      .map((item) => {
        const photo = item.photo_url || "";
        const inCart = cart.find((row) => cartKey(row) === cartKey(item));
        const currentQty = inCart?.qty || 0;
        const outOfStock = stockNumber(item.stock) === 0;
        const atLimit = !canAddMore(item, currentQty);
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
                  ${renderPriceHtml(item)}
                  ${stockLabel(item.stock)}
                </div>
                <button class="icon-btn" data-add="${encodeURIComponent(JSON.stringify(item))}" ${disabled} title="В кошик">🛒</button>
              </div>
            </div>
          </article>
        `;
      })
      .join("");
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
    const receiptFile = els.paymentReceipt?.files?.[0] || null;
    const ttnPdfFile = els.ttnPdf?.files?.[0] || null;
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
      ttnNumber:
        selectedOwnTtnCarrier() === "rozetka"
          ? normalizeRmpNumber(form.rmpNumber?.value || "")
          : (form.ttnNumber?.value || "").replace(/\D/g, ""),
      rmpNumber: normalizeRmpNumber(form.rmpNumber?.value || ""),
      paymentMethod,
      codAmount: form.codAmount?.value?.trim() || "",
      prepay: form.prepay.value.trim(),
      comment: form.comment.value.trim(),
      rulesAccepted: Boolean(form.rulesAccepted.checked),
      receiptName: receiptFile ? receiptFile.name : "",
      receiptFile,
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
    }

    if (
      data.paymentMethod === "requisites" &&
      dropperSettings.require_full_payment &&
      !data.receiptFile
    ) {
      return "Завантажте фото/скрін квитанції про оплату";
    }
    if (!data.rulesAccepted) {
      return "Підтвердіть ознайомлення з правилами";
    }

    if (data.paymentMethod === "balance") {
      if (!dropperSettings.allow_balance_payment) {
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
      const codRaw = data.codAmount === "" ? null : Number(data.codAmount);
      if (codRaw === null || Number.isNaN(codRaw) || codRaw < 0) {
        return "Вкажіть суму накладного платежу";
      }
      data.codAmount = Math.round(codRaw);

      const prepay = data.prepay === "" ? 0 : Number(data.prepay);
      if (Number.isNaN(prepay) || prepay < 0) {
        return "Некоректна сума передплати";
      }
      if (prepay > data.codAmount) {
        return "Передплата не може перевищувати суму накладного платежу";
      }
      const maxPrepay = maxPrepayAmount(data.total);
      if (prepay > maxPrepay) {
        if (dropperSettings.allow_balance_payment) {
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
    const codExact =
      data.paymentMethod === "cod" ? roundMoney(data.codAmount || 0) : 0;
    const prepayExact =
      data.paymentMethod === "cod"
        ? roundMoney(data.prepay === "" ? 0 : data.prepay || 0)
        : 0;
    const dropperProfit =
      data.paymentMethod === "cod"
        ? roundMoney(codExact - prepayExact - totalExact)
        : null;
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
    els.confirmSummary.innerHTML = `
      ${recipientBlock}
      <div class="confirm-block">
        <div class="confirm-label">Оплата</div>
        <div class="confirm-value">${escapeHtml(paymentMethodLabel(data.paymentMethod))}
Дроп ціна: ${escapeHtml(formatMoneyAmount(totalExact))} ₴
${
  data.paymentMethod === "cod"
    ? `Накладений платіж: ${escapeHtml(formatMoneyAmount(codExact))} ₴\nПередплата: ${escapeHtml(formatMoneyAmount(prepayExact))} ₴\nПрибуток дроппера: ${escapeHtml(formatMoneyAmount(dropperProfit))} ₴`
    : ""
}
${debit > 0 ? `З балансу спишеться: ${escapeHtml(formatMoneyAmount(debit))} ₴` : ""}
${
  data.ownTtn
    ? data.ownTtnCarrier === "rozetka"
      ? `Власний RMP: ${escapeHtml(data.ttnNumber || data.rmpNumber || "")}`
      : `Власна ТТН НП: ${escapeHtml(data.ttnNumber || "")}`
    : "ТТН: створиться пізніше (НП)"
}</div>
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
      payment_method: data.paymentMethod,
      prepay: data.prepay === "" ? 0 : Number(data.prepay || 0),
      cod_amount: Number(data.codAmount || 0),
      comment: data.comment || "",
      receipt_name: data.receiptName || "",
      ttn_pdf_name: data.ttnPdfName || "",
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

  /** Статус для бейджа в історії замовлень (українською). */
  function orderHistoryStatus(order) {
    const payload = order.payload || {};
    const ttn = String(order.ttn_status || "");
    const hasTtn = Boolean(order.ttn_number || payload.ttn_number);

    if (payload.return_at_warehouse || ttn === "return_at_warehouse") {
      return { kind: "return_warehouse", label: "Отримано повернення на склад", sub: "" };
    }
    if (
      payload.dropper_return ||
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

  function renderOrderDetailsHtml(order) {
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
      </div>
    `;
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

  function renderOrderCard(order, { compact = false } = {}) {
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
          ${renderOrderDetailsHtml(order)}
        </div>
      </article>
    `;
  }

  function bindOrderCardClicks(root) {
    if (!root || root.dataset.orderClicksBound === "1") return;
    root.dataset.orderClicksBound = "1";
    root.addEventListener("click", (event) => {
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

  async function renderOrdersHistory() {
    if (!els.ordersHistory) return;
    const chatId = effectiveDropperChatId();
    els.ordersHistory.innerHTML = `<div class="ac-loading">Завантаження історії...</div>`;
    try {
      const response = await fetch(
        `/api/dropper/orders?chat_id=${encodeURIComponent(chatId)}&limit=50`
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
      }
      const items = data.items || [];
      els.ordersHistory.innerHTML = items.length
        ? items.map((o) => renderOrderCard(o)).join("")
        : `<div class="empty">Поки немає переданих замовлень</div>`;
      bindOrderCardClicks(els.ordersHistory);
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
          `/api/owner/droppers/${encodeURIComponent(chatId)}/orders?${ownerAuthParams()}&limit=100`
        );
        const data = await response.json();
        if (!response.ok) {
          throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
        }
        box._ordersCache = data.items || [];
        box.dataset.loaded = "1";
      } catch (error) {
        box.innerHTML = `<div class="form-error">${escapeHtml(error.message || "Помилка")}</div>`;
        return;
      }
    }

    renderOwnerDropperOrdersPanel(box);
  }

  function ownerOrderFilterValues(box) {
    return {
      productCode: box.querySelector("[data-filter-code]")?.value?.trim() || "",
      orderNumber: box.querySelector("[data-filter-order]")?.value?.trim() || "",
      phone: box.querySelector("[data-filter-phone]")?.value?.trim() || "",
      clientName: box.querySelector("[data-filter-name]")?.value?.trim() || "",
      ttnNumber: box.querySelector("[data-filter-ttn]")?.value?.trim() || "",
      dateFrom: box.querySelector("[data-filter-date-from]")?.value || "",
      dateTo: box.querySelector("[data-filter-date-to]")?.value || "",
    };
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

  function renderOwnerDropperOrdersPanel(box) {
    const all = Array.isArray(box._ordersCache) ? box._ordersCache : [];

    if (!box.querySelector("[data-owner-order-filters]")) {
      box.innerHTML = `
        <p class="owner-orders-title">Історія замовлень</p>
        <div class="owner-orders-filters" data-owner-order-filters>
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
          renderOwnerDropperOrdersList(box);
        });
        box.addEventListener("change", (event) => {
          if (!event.target.closest("[data-owner-order-filters]")) return;
          renderOwnerDropperOrdersList(box);
        });
        box.addEventListener("click", (event) => {
          const reset = event.target.closest("[data-filter-reset]");
          if (!reset || !box.contains(reset)) return;
          box.querySelectorAll("[data-owner-order-filters] input").forEach((input) => {
            input.value = "";
          });
          renderOwnerDropperOrdersList(box);
        });
      }
    }

    renderOwnerDropperOrdersList(box);
  }

  function renderOwnerDropperOrdersList(box) {
    const all = Array.isArray(box._ordersCache) ? box._ordersCache : [];
    const filters = ownerOrderFilterValues(box);
    const filtered = all.filter((o) => orderMatchesOwnerFilters(o, filters));
    const countEl = box.querySelector("[data-orders-count]");
    const listEl = box.querySelector("[data-owner-orders-list]");
    if (countEl) {
      countEl.textContent = `Показано ${filtered.length} з ${all.length}`;
    }
    if (listEl) {
      listEl.innerHTML = filtered.length
        ? filtered.map((o) => renderOrderCard(o, { compact: true })).join("")
        : `<div class="empty">${
            all.length ? "Нічого не знайдено за фільтрами" : "Замовлень ще немає"
          }</div>`;
      bindOrderCardClicks(listEl);
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

  document.querySelectorAll(".tab").forEach((tab) => {
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
  bindFilePicker(els.paymentReceipt, els.paymentReceiptName);

  els.checkoutForm.addEventListener("change", (event) => {
    if (event.target.name === "deliveryMethod") syncDeliveryFields();
    if (
      event.target.id === "ownTtn" ||
      event.target.name === "paymentMethod" ||
      event.target.name === "ownTtnCarrier"
    ) {
      syncPaymentAndTtn();
    }
  });

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
    const allowed = new Set(["droppers", "staff", "balances", "settings", "order", "blacklist"]);
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
        if (dropper.allow_balance_payment) {
          bits.push(
            `<div class="balance-stat"><span class="balance-stat-label">Доступно до списання</span><span class="balance-stat-value">${escapeHtml(
              formatMoney(spendRoom)
            )}</span></div>`
          );
        }
        if (programOn && dropper.referral_code) {
          bits.push(
            `<div class="balance-stat"><span class="balance-stat-label">Ваш реферальний код</span><span class="balance-stat-value">${escapeHtml(
              dropper.referral_code
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
          (programOn
            ? "Усі нарахування та списання: оплата з балансу, передплата понад «Дроп ціна», реферали тощо."
            : "Усі нарахування та списання: оплата з балансу, передплата понад «Дроп ціна» тощо.");
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
      const items = data.items || [];
      els.ownerBlacklist.innerHTML = items.length
        ? items
            .map(
              (row) => `
          <article class="owner-card blacklist-card">
            <div class="owner-card-head">
              <div class="owner-card-title">${escapeHtml(row.phone_display || row.phone_digits)}</div>
              ${
                row.note
                  ? `<div class="meta">${escapeHtml(row.note)}</div>`
                  : ""
              }
              <div class="meta-soft">${escapeHtml(row.created_at || "")}</div>
            </div>
            <button type="button" class="btn secondary" data-blacklist-del="${escapeHtml(
              String(row.id)
            )}">Видалити</button>
          </article>`
            )
            .join("")
        : `<div class="empty">Чорний список порожній</div>`;
    } catch (error) {
      els.ownerBlacklist.innerHTML = `<div class="form-error">${escapeHtml(
        error.message || "Помилка"
      )}</div>`;
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
                      d.allow_cod !== false ? "checked" : ""
                    } />
                    <span class="toggle-ui"></span>
                  </span>
                </span>
              </label>
              <label class="setting-row">
                <span class="setting-copy">
                  <span class="setting-label">Лише після повної оплати</span>
                  <span class="setting-hint">Потрібна квитанція до замовлення</span>
                </span>
                <span class="setting-control">
                  <span class="toggle">
                    <input type="checkbox" data-rule="require_full_payment" ${
                      d.require_full_payment ? "checked" : ""
                    } />
                    <span class="toggle-ui"></span>
                  </span>
                </span>
              </label>
              <label class="setting-row">
                <span class="setting-copy">
                  <span class="setting-label">В рахунок балансу</span>
                  <span class="setting-hint">Списання з балансу замість оплати</span>
                </span>
                <span class="setting-control">
                  <span class="toggle">
                    <input type="checkbox" data-rule="allow_balance_payment" ${
                      d.allow_balance_payment ? "checked" : ""
                    } />
                    <span class="toggle-ui"></span>
                  </span>
                </span>
              </label>
              <label class="setting-row">
                <span class="setting-copy">
                  <span class="setting-label">Мінус-баланс дозволено</span>
                  <span class="setting-hint">Можна йти в мінус до ліміту</span>
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
      if (sessionState.role === "admin" || sessionState.role === "manager" || sessionState.role === "warehouse") {
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
        referral_code: (document.getElementById("regReferral")?.value || "").trim(),
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

  if (els.ownerBlacklist) {
    els.ownerBlacklist.addEventListener("click", async (event) => {
      const btn = event.target.closest("[data-blacklist-del]");
      if (!btn || !els.ownerBlacklist.contains(btn)) return;
      const id = btn.getAttribute("data-blacklist-del");
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
      }
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
          const enabled = Boolean(check.checked);
          if (percentRow && percentInput) {
            percentRow.classList.toggle("is-disabled", !enabled);
            percentInput.disabled = !enabled;
          }
          if (monthsRow && monthsInput) {
            monthsRow.classList.toggle("is-disabled", !enabled);
            monthsInput.disabled = !enabled;
          }
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
            const enabled = Boolean(check.checked);
            if (percentRow && percentInput) {
              percentRow.classList.toggle("is-disabled", !enabled);
              percentInput.disabled = !enabled;
            }
            if (monthsRow && monthsInput) {
              monthsRow.classList.toggle("is-disabled", !enabled);
              monthsInput.disabled = !enabled;
            }
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
