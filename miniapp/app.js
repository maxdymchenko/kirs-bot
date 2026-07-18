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

  // Реквізити для оплати — підставте реальні дані бізнесу
  const PAYMENT_REQUISITES = {
    recipient: "ФОП (вкажіть отримувача)",
    edrpou: "0000000000",
    iban: "UA000000000000000000000000000",
    bank: "АТ КБ «ПРИВАТБАНК»",
    purpose: "Назва товару, скорочено",
  };

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
    ownerTabOrder: document.getElementById("ownerTabOrder"),
    ownerDroppers: document.getElementById("ownerDroppers"),
    ownerStaff: document.getElementById("ownerStaff"),
    ownerBalances: document.getElementById("ownerBalances"),
    ownerReferralHistory: document.getElementById("ownerReferralHistory"),
    balanceView: document.getElementById("balanceView"),
    balanceHero: document.getElementById("balanceHero"),
    balanceReferralTotal: document.getElementById("balanceReferralTotal"),
    balanceLedger: document.getElementById("balanceLedger"),
    balanceHint: document.getElementById("balanceHint"),
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
    mainTabs: document.getElementById("mainTabs"),
    cartList: document.getElementById("cartList"),
    cartEmpty: document.getElementById("cartEmpty"),
    cartFooter: document.getElementById("cartFooter"),
    cartCount: document.getElementById("cartCount"),
    cartSum: document.getElementById("cartSum"),
    cartBadge: document.getElementById("cartBadge"),
    cartChipText: document.getElementById("cartChipText"),
    cartChip: document.getElementById("cartChip"),
    checkoutBtn: document.getElementById("checkoutBtn"),
    checkoutBack: document.getElementById("checkoutBack"),
    checkoutForm: document.getElementById("checkoutForm"),
    checkoutError: document.getElementById("checkoutError"),
    firstName: document.getElementById("firstName"),
    patronymic: document.getElementById("patronymic"),
    patronymicHint: document.getElementById("patronymicHint"),
    lastName: document.getElementById("lastName"),
    ownTtn: document.getElementById("ownTtn"),
    ttnFields: document.getElementById("ttnFields"),
    ttnNumber: document.getElementById("ttnNumber"),
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
    prepayMaxLabel: document.getElementById("prepayMaxLabel"),
    prepay: document.getElementById("prepay"),
    requisitesBlock: document.getElementById("requisitesBlock"),
    requisitesDetails: document.getElementById("requisitesDetails"),
    payAmountLabel: document.getElementById("payAmountLabel"),
    paymentReceipt: document.getElementById("paymentReceipt"),
    receiptField: document.getElementById("receiptField"),
    requisitesIntro: document.getElementById("requisitesIntro"),
    ttnPdfField: document.getElementById("ttnPdfField"),
    ttnPdf: document.getElementById("ttnPdf"),
    phone: document.getElementById("phone"),
    phoneGhost: document.getElementById("phoneGhost"),
    city: document.getElementById("city"),
    cityRef: document.getElementById("cityRef"),
    settlementRef: document.getElementById("settlementRef"),
    cityDropdown: document.getElementById("cityDropdown"),
    warehouse: document.getElementById("warehouse"),
    warehouseRef: document.getElementById("warehouseRef"),
    warehouseDropdown: document.getElementById("warehouseDropdown"),
  };

  const dropperSettings = {
    chat_id: "",
    require_full_payment: false,
    allow_balance_payment: false,
    allow_negative_balance: false,
    negative_balance_limit: 0,
    extra_discount_percent: 0,
    orders_disabled: false,
    referral_code: "",
    referral_percent: 0,
  };

  const sessionState = {
    role: "guest",
    chat_id: "",
    user_id: "",
    username: "",
    need_registration: false,
  };

  const PHONE_EXAMPLE = "+380(99)999-99-99";
  const PHONE_PREFIX_DIGITS = "380";
  const PHONE_MAX_DIGITS = 12;
  const PHONE_PREFIX_DISPLAY = "+380(";

  const npState = {
    city: null,
    warehouse: null,
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

  function cartQtyTotal(cart = loadCart()) {
    return cart.reduce((sum, item) => sum + (item.qty || 1), 0);
  }

  function cartMoneyTotal(cart = loadCart()) {
    return cart.reduce(
      (sum, item) => sum + parsePrice(item.drop_price) * (item.qty || 1),
      0
    );
  }

  function formatMoney(amount) {
    return `${Math.round(amount)} ₴`;
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
    return formatted;
  }

  function resetPhoneField() {
    setPhoneDigits(PHONE_PREFIX_DIGITS);
  }

  function isPhoneComplete() {
    return phoneDigits.length === PHONE_MAX_DIGITS;
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

  function switchTab(name) {
    if (els.mainTabs) {
      els.mainTabs.querySelectorAll("[data-tab]").forEach((tab) => {
        tab.classList.toggle("active", tab.dataset.tab === name);
      });
    }
    els.mainTabs.classList.remove("hidden");
    els.catalogView.classList.toggle("hidden", name !== "catalog");
    els.cartView.classList.toggle("hidden", name !== "cart");
    els.checkoutView.classList.add("hidden");
    if (name === "cart") renderCart();
  }

  async function openCheckout() {
    const cart = loadCart();
    if (!cart.length) return;
    els.catalogView.classList.add("hidden");
    els.cartView.classList.add("hidden");
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

  async function searchWarehouses(query) {
    const cityRef = npState.city?.city_ref || els.cityRef.value;
    if (!cityRef) return;
    const reqId = ++npState.warehouseReq;
    showDropdownMessage(els.warehouseDropdown, "Шукаємо...", "ac-loading");
    try {
      const response = await fetch(
        `/api/np/warehouses?city_ref=${encodeURIComponent(cityRef)}&q=${encodeURIComponent(query)}&limit=200`
      );
      const data = await response.json();
      if (reqId !== npState.warehouseReq) return;
      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string" ? data.detail : "Помилка пошуку відділень"
        );
      }
      renderWarehouseOptions(data.items || []);
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
    // Порожній запит = показати всі доступні відділення в місті
    npState.warehouseTimer = setTimeout(() => searchWarehouses(query), query ? 280 : 0);
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
    els.requisitesDetails.innerHTML = `
      <div><strong>Отримувач:</strong> ${escapeHtml(PAYMENT_REQUISITES.recipient)}</div>
      <div><strong>ЄДРПОУ:</strong> ${escapeHtml(PAYMENT_REQUISITES.edrpou)}</div>
      <div><strong>Рахунок IBAN:</strong> ${escapeHtml(PAYMENT_REQUISITES.iban)}</div>
      <div><strong>Банк:</strong> ${escapeHtml(PAYMENT_REQUISITES.bank)}</div>
      <div><strong>Призначення:</strong> ${escapeHtml(PAYMENT_REQUISITES.purpose)}</div>
    `;
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

  async function loadDropperSettings() {
    const chatId = currentTelegramChatId();
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
      dropperSettings.allow_balance_payment = Boolean(data.allow_balance_payment);
      dropperSettings.allow_negative_balance = Boolean(data.allow_negative_balance);
      dropperSettings.negative_balance_limit = Number(data.negative_balance_limit || 0);
      dropperSettings.extra_discount_percent = Number(data.extra_discount_percent || 0);
      dropperSettings.orders_disabled = Boolean(data.orders_disabled);
      dropperSettings.referral_code = data.referral_code || "";
      dropperSettings.referral_percent = Number(data.referral_percent || 0);
      if (data.chat_id) dropperSettings.chat_id = String(data.chat_id);
    } catch (error) {
      console.warn("dropper settings", error);
      dropperSettings.require_full_payment = false;
      dropperSettings.allow_balance_payment = false;
      dropperSettings.allow_negative_balance = false;
      dropperSettings.negative_balance_limit = 0;
      dropperSettings.extra_discount_percent = 0;
      dropperSettings.orders_disabled = false;
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
    const amount = `${Math.round(total)} грн`;
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

  function syncPaymentAndTtn() {
    const ownTtn = Boolean(els.ownTtn.checked);
    els.ttnFields.classList.toggle("hidden", !ownTtn);

    // При власній ТТН — лише оплата на реквізити
    els.codPaymentCard.classList.toggle("hidden", ownTtn);
    els.codPaymentHint.classList.toggle("hidden", ownTtn);

    if (ownTtn) {
      const req = els.checkoutForm.querySelector('input[name="paymentMethod"][value="requisites"]');
      if (req) req.checked = true;
    }

    const payment = selectedPaymentMethod();
    const showRequisites = payment === "requisites";
    const showPrepay = !ownTtn && payment === "cod";
    const showReceipt = showRequisites && dropperSettings.require_full_payment;

    els.prepayBlock.classList.toggle("hidden", !showPrepay);
    els.requisitesBlock.classList.toggle("hidden", !showRequisites);
    els.receiptField.classList.toggle("hidden", !showReceipt);
    els.ttnPdfField.classList.toggle("hidden", !ownTtn);

    const total = Math.round(cartMoneyTotal());
    els.prepayMaxLabel.textContent = String(total);
    els.prepay.max = String(total);
    updateRequisitesIntro(total);
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

  function renderResults(items) {
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
        const price = item.drop_price ? `${item.drop_price} ₴` : "—";
        const priceExtra =
          item.drop_price_original != null
            ? `<div class="meta-soft">було ${escapeHtml(String(item.drop_price_original))} ₴ (−${escapeHtml(
                String(item.extra_discount_percent || 0)
              )}%)</div>`
            : "";
        const inCart = cart.find((row) => cartKey(row) === cartKey(item));
        const currentQty = inCart?.qty || 0;
        const outOfStock = stockNumber(item.stock) === 0;
        const atLimit = !canAddMore(item, currentQty);
        const disabled = outOfStock || atLimit ? "disabled" : "";
        return `
          <article class="card">
            <img src="${photo || ""}" alt="" onerror="this.style.opacity=0.2" />
            <div class="card-body">
              <div class="card-title">${escapeHtml(item.name || "")}</div>
              <div class="meta">Код: <b>${escapeHtml(item.code || "")}</b> · ${escapeHtml(item.color || "без кольору")}</div>
              <div class="row-actions">
                <div>
                  <div class="price">${escapeHtml(price)}</div>
                  ${priceExtra}
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
        const price = item.drop_price ? `${item.drop_price} ₴` : "—";
        const qty = item.qty || 1;
        const plusDisabled = canAddMore(item, qty) ? "" : "disabled";
        return `
          <article class="card">
            <img src="${photo}" alt="" onerror="this.style.opacity=0.2" />
            <div class="card-body">
              <div class="card-title">${escapeHtml(item.name || "")}</div>
              <div class="meta">Код: <b>${escapeHtml(item.code || "")}</b> · ${escapeHtml(item.color || "без кольору")}</div>
              <div class="row-actions">
                <div>
                  <div class="price">${escapeHtml(price)}</div>
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
      ttnNumber: (form.ttnNumber?.value || "").replace(/\D/g, ""),
      paymentMethod,
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
    if (!data.firstName) return "Вкажіть ім'я отримувача";
    if (!data.lastName) return "Вкажіть прізвище отримувача";
    if (!data.phone || !isPhoneComplete()) {
      return "Вкажіть повний телефон у форматі +380(XX)XXX-XX-XX";
    }
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
    if (data.ownTtn) {
      if (!data.ttnNumber) return "Вкажіть номер ТТН";
      if (!/^\d+$/.test(data.ttnNumber)) {
        return "Номер ТТН має містити лише цифри";
      }
      if (data.ttnNumber.length < 10) {
        return "Вкажіть повний номер ТТН";
      }
      if (data.paymentMethod !== "requisites") {
        return "При власній ТТН доступна лише оплата на реквізити";
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
    if (!data.ownTtn && data.paymentMethod === "cod") {
      const prepay = data.prepay === "" ? 0 : Number(data.prepay);
      if (Number.isNaN(prepay) || prepay < 0) {
        return "Некоректна сума передплати";
      }
      if (prepay > data.total) {
        return `Передплата не може перевищувати ${Math.round(data.total)} грн`;
      }
    }
    return "";
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
      const chatId = currentTelegramChatId();
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
    const btn = event.target.closest("[data-add]");
    if (!btn || btn.disabled) return;
    try {
      const item = JSON.parse(decodeURIComponent(btn.getAttribute("data-add")));
      addToCart(item);
      updateCartIndicators();
    } catch {
      showToast("Не вдалося додати товар");
    }
  });

  els.cartList.addEventListener("click", (event) => {
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

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => switchTab(tab.dataset.tab));
  });

  els.cartChip.addEventListener("click", () => switchTab("cart"));
  els.checkoutBtn.addEventListener("click", openCheckout);
  els.checkoutBack.addEventListener("click", () => switchTab("cart"));

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

  els.checkoutForm.addEventListener("change", (event) => {
    if (event.target.name === "deliveryMethod") syncDeliveryFields();
    if (event.target.id === "ownTtn" || event.target.name === "paymentMethod") {
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
    // Поки що тільки збираємо дані; відправка на бекенд — наступний етап
    console.log("checkout draft", data);
    showToast("Дані зібрано. Підтвердження замовлення — наступний етап");
    safeTgAlert(
      "Форма заповнена. Далі додамо підтвердження та відправку замовлення."
    );
  });

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
    const allowed = new Set(["droppers", "staff", "balances", "order"]);
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
    if (els.ownerTabOrder) {
      els.ownerTabOrder.classList.toggle("hidden", name !== "order");
    }

    const showOrder = name === "order";
    if (els.orderMain) els.orderMain.classList.toggle("hidden", !showOrder);
    if (els.mainTabs) els.mainTabs.classList.toggle("hidden", !showOrder);
    if (els.cartChip) els.cartChip.classList.toggle("hidden", !showOrder);

    if (name === "balances") {
      renderOwnerBalances();
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

  async function renderBalanceView() {
    if (!els.balanceView) return;
    els.balanceHero.textContent = "…";
    els.balanceLedger.innerHTML = `<div class="ac-loading">Завантаження...</div>`;
    try {
      const chatId = currentTelegramChatId();
      const response = await fetch(
        `/api/dropper/balance?chat_id=${encodeURIComponent(chatId)}`
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Помилка балансу");
      els.balanceHero.textContent = formatMoney(data.balance || 0);
      els.balanceReferralTotal.textContent = `Реферально нараховано: ${formatMoney(
        data.referral_earned_total || 0
      )}`;
      if (data.note && els.balanceHint) els.balanceHint.textContent = data.note;
      const rows = data.ledger || [];
      els.balanceLedger.innerHTML = rows.length
        ? rows
            .map(
              (r) => `
          <article class="owner-card">
            <div class="owner-card-title">${escapeHtml(r.title || r.entry_type)}</div>
            <div class="meta">${formatLedgerAmount(r.amount)}</div>
            <div class="meta-soft">${escapeHtml(r.note || "")}</div>
            <div class="meta-soft">${escapeHtml(r.created_at || "")}</div>
          </article>`
            )
            .join("")
        : `<div class="empty">Поки немає нарахувань. Реферали з’являться після замовлень приведених дропперів.</div>`;
    } catch (error) {
      els.balanceHero.textContent = "—";
      els.balanceLedger.innerHTML = `<div class="form-error">${escapeHtml(
        error.message || "Помилка"
      )}</div>`;
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
            <article class="owner-card">
              <div class="owner-card-title">${escapeHtml(d.company_name || "")}</div>
              <div class="meta">Баланс: <b>${escapeHtml(formatMoney(row.balance || 0))}</b></div>
              <div class="meta-soft">Реф. нараховано: ${escapeHtml(
                formatMoney(row.referral_earned_total || 0)
              )} · код ${escapeHtml(d.referral_code || "—")}</div>
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
          <article class="owner-card" data-dropper-chat="${escapeHtml(d.chat_id)}">
            <div class="owner-card-head">
              <h3 class="owner-card-title">${escapeHtml(d.company_name)}</h3>
              <p class="meta">${escapeHtml(d.contact_name)} · ${escapeHtml(d.phone)}</p>
              <p class="meta">chat_id: <b>${escapeHtml(d.chat_id)}</b></p>
              <p class="meta">
                Реф. код: <b>${escapeHtml(d.referral_code || "—")}</b>
                ${d.referred_by_name ? ` · запрошений: ${escapeHtml(d.referred_by_name)}` : ""}
                ${d.referrals_count ? ` · привів: ${escapeHtml(String(d.referrals_count))}` : ""}
              </p>
            </div>
            <div class="owner-settings">
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
              <label class="setting-row is-nested">
                <span class="setting-copy">
                  <span class="setting-label">Ліміт мінусу</span>
                  <span class="setting-hint">Максимальний борг, ₴</span>
                </span>
                <span class="setting-control">
                  <input class="setting-input" type="number" min="0" step="1"
                    data-rule-num="negative_balance_limit"
                    value="${escapeHtml(String(d.negative_balance_limit || 0))}" />
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
                  <span class="setting-label">Реферальний %</span>
                  <span class="setting-hint">З дроп-ціни приведених</span>
                </span>
                <span class="setting-control">
                  <input class="setting-input" type="number" min="0" max="100" step="0.1"
                    data-rule-num="referral_percent"
                    value="${escapeHtml(String(d.referral_percent || 0))}" />
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
            <div class="meta">${escapeHtml(staffRoleLabel(s.role))} · user_id: ${escapeHtml(
                s.telegram_user_id
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

  function showMode(mode) {
    els.bootStatus.classList.add("hidden");
    els.registerView.classList.add("hidden");
    els.ownerView.classList.add("hidden");
    els.orderMain.classList.add("hidden");
    els.mainTabs.classList.add("hidden");
    els.cartChip.classList.add("hidden");
    if (els.balanceView) els.balanceView.classList.add("hidden");

    if (mode === "register") {
      els.registerView.classList.remove("hidden");
      return;
    }
    if (mode === "owner") {
      els.ownerView.classList.remove("hidden");
      const initial =
        queryParam("view") === "balances" || queryParam("view") === "balance"
          ? "balances"
          : "droppers";
      setOwnerTab(initial);
      renderOwnerCabinet();
      return;
    }
    if (mode === "balance") {
      if (els.balanceView) els.balanceView.classList.remove("hidden");
      renderBalanceView();
      return;
    }
    if (mode === "dropper") {
      if (queryParam("view") === "balance") {
        if (els.balanceView) els.balanceView.classList.remove("hidden");
        renderBalanceView();
        return;
      }
      els.orderMain.classList.remove("hidden");
      els.mainTabs.classList.remove("hidden");
      els.cartChip.classList.remove("hidden");
      loadColorOptions();
      loadDropperSettings().then(() => {
        syncPaymentAndTtn();
        updateCartIndicators();
      });
      return;
    }
    if (mode === "dropper_blocked") {
      els.bootStatus.classList.remove("hidden");
      els.bootStatus.innerHTML =
        `<div class="blocked-box">Вас заблоковано для повного погашення боргу.<br/>Передача замовлень недоступна. Звʼяжіться з власником.</div>`;
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
        )}`
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "session error");
      sessionState.role = data.role || "guest";
      sessionState.need_registration = Boolean(data.need_registration);
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

  if (els.staffForm) {
    els.staffForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      els.staffError.classList.add("hidden");
      const payload = {
        ...ownerAuthBody(),
        telegram_user_id: document.getElementById("staffUserId").value.trim(),
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

    els.ownerDroppers.addEventListener("change", async (event) => {
      const card = event.target.closest("[data-dropper-chat]");
      if (!card) return;
      const check = event.target.closest("[data-rule]");
      const num = event.target.closest("[data-rule-num]");
      if (check) {
        const key = check.getAttribute("data-rule");
        const prev = !check.checked;
        await persistRule(card, { [key]: Boolean(check.checked) }, () => {
          check.checked = prev;
        });
        return;
      }
      if (num) {
        const key = num.getAttribute("data-rule-num");
        let value = Number(num.value);
        if (!Number.isFinite(value) || value < 0) value = 0;
        if (
          (key === "extra_discount_percent" || key === "referral_percent") &&
          value > 100
        ) {
          value = 100;
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
