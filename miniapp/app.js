(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
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
    ownerDroppers: document.getElementById("ownerDroppers"),
    ownerStaff: document.getElementById("ownerStaff"),
    staffForm: document.getElementById("staffForm"),
    staffError: document.getElementById("staffError"),
    orderMain: document.getElementById("orderMain"),
    searchForm: document.getElementById("searchForm"),
    searchInput: document.getElementById("searchInput"),
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
    document.querySelectorAll(".tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.tab === name);
    });
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
        `/api/np/warehouses?city_ref=${encodeURIComponent(cityRef)}&q=${encodeURIComponent(query)}&limit=50`
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
    if (!npState.city?.city_ref) return;
    if (query.length < 1) {
      hideDropdown(els.warehouseDropdown);
      return;
    }
    npState.warehouseTimer = setTimeout(() => searchWarehouses(query), 300);
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

  function currentTelegramChatId() {
    if (sessionState.chat_id) return sessionState.chat_id;
    const unsafe = tg?.initDataUnsafe || {};
    if (unsafe.chat?.id != null) return String(unsafe.chat.id);
    return "";
  }

  function currentTelegramUser() {
    const unsafe = tg?.initDataUnsafe || {};
    return {
      user_id: sessionState.user_id || (unsafe.user?.id != null ? String(unsafe.user.id) : ""),
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
      if (data.chat_id) dropperSettings.chat_id = String(data.chat_id);
    } catch (error) {
      console.warn("dropper settings", error);
      dropperSettings.require_full_payment = false;
    }
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

  function stockLabel(stock) {
    if (stock === null || stock === undefined || stock === "") {
      return `<span class="stock-ok">Наявність: —</span>`;
    }
    if (Number(stock) <= 0) {
      return `<span class="stock-out">Немає в наявності</span>`;
    }
    return `<span class="stock-ok">В наявності: ${stock}</span>`;
  }

  function renderResults(items) {
    if (!items.length) {
      els.results.innerHTML = "";
      els.status.textContent = "Нічого не знайдено за цим кодом";
      return;
    }

    els.status.textContent = `Знайдено варіантів: ${items.length}`;
    els.results.innerHTML = items
      .map((item) => {
        const photo = item.photo_url || "";
        const price = item.drop_price ? `${item.drop_price} ₴` : "—";
        const disabled = Number(item.stock) === 0 ? "disabled" : "";
        return `
          <article class="card">
            <img src="${photo || ""}" alt="" onerror="this.style.opacity=0.2" />
            <div class="card-body">
              <div class="card-title">${escapeHtml(item.name || "")}</div>
              <div class="meta">Код: <b>${escapeHtml(item.code || "")}</b> · ${escapeHtml(item.color || "без кольору")}</div>
              <div class="row-actions">
                <div>
                  <div class="price">${escapeHtml(price)}</div>
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

  function renderCart() {
    const cart = loadCart();
    if (!cart.length) {
      els.cartEmpty.classList.remove("hidden");
      els.cartList.innerHTML = "";
      els.cartFooter.classList.add("hidden");
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
        return `
          <article class="card">
            <img src="${photo}" alt="" onerror="this.style.opacity=0.2" />
            <div class="card-body">
              <div class="card-title">${escapeHtml(item.name || "")}</div>
              <div class="meta">Код: <b>${escapeHtml(item.code || "")}</b> · ${escapeHtml(item.color || "без кольору")}</div>
              <div class="row-actions">
                <div class="price">${escapeHtml(price)}</div>
                <div class="qty">
                  <button type="button" data-dec="${index}">−</button>
                  <strong>${item.qty || 1}</strong>
                  <button type="button" data-inc="${index}">+</button>
                  <button type="button" data-del="${index}" title="Видалити">✕</button>
                </div>
              </div>
            </div>
          </article>
        `;
      })
      .join("");
  }

  function addToCart(item) {
    const cart = loadCart();
    const key = cartKey(item);
    const existing = cart.find((row) => cartKey(row) === key);
    if (existing) {
      existing.qty = (existing.qty || 1) + 1;
    } else {
      cart.push({ ...item, qty: 1 });
    }
    saveCart(cart);
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
    const code = els.searchInput.value.trim();
    if (!code) return;

    els.status.textContent = "Шукаємо...";
    els.results.innerHTML = "";

    try {
      const response = await fetch(`/api/products/search?code=${encodeURIComponent(code)}`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Помилка пошуку");
      }
      renderResults(data.items || []);
    } catch (error) {
      els.status.textContent = error.message || "Помилка пошуку";
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
    }
    if (inc) {
      const i = Number(inc.dataset.inc);
      cart[i].qty = (cart[i].qty || 1) + 1;
      saveCart(cart);
      renderCart();
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
    if (!els.warehouse.disabled && els.warehouse.value.trim().length >= 1 && !npState.warehouse) {
      scheduleWarehouseSearch(els.warehouse.value);
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
    if (tg?.showAlert) {
      tg.showAlert(
        "Форма заповнена. Далі додамо підтвердження та відправку замовлення."
      );
    }
  });

  async function renderOwnerCabinet() {
    const chatId = currentTelegramChatId();
    els.ownerDroppers.innerHTML = `<div class="ac-loading">Завантаження дропперів...</div>`;
    els.ownerStaff.innerHTML = "";
    try {
      const [droppersRes, staffRes] = await Promise.all([
        fetch(`/api/owner/droppers?owner_chat_id=${encodeURIComponent(chatId)}`),
        fetch(`/api/owner/staff?owner_chat_id=${encodeURIComponent(chatId)}`),
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
          <article class="owner-card">
            <div class="owner-card-title">${escapeHtml(d.company_name)}</div>
            <div class="meta">${escapeHtml(d.contact_name)} · ${escapeHtml(d.phone)}</div>
            <div class="meta">chat_id: <b>${escapeHtml(d.chat_id)}</b></div>
            <label class="switch-row">
              <span>Лише після повної оплати</span>
              <input type="checkbox" data-pay-flag="${escapeHtml(d.chat_id)}" ${
                d.require_full_payment ? "checked" : ""
              } />
            </label>
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
            <div class="meta">role: <b>${escapeHtml(s.role)}</b> · user_id: ${escapeHtml(
                s.telegram_user_id
              )}</div>
          </article>`
            )
            .join("")
        : `<div class="empty">Співробітників ще немає</div>`;
    } catch (error) {
      els.ownerDroppers.innerHTML = `<div class="form-error">${escapeHtml(
        error.message || "Помилка"
      )}</div>`;
    }
  }

  function showMode(mode) {
    els.bootStatus.classList.add("hidden");
    els.registerView.classList.add("hidden");
    els.ownerView.classList.add("hidden");
    els.orderMain.classList.add("hidden");
    els.mainTabs.classList.add("hidden");
    els.cartChip.classList.add("hidden");

    if (mode === "register") {
      els.registerView.classList.remove("hidden");
      return;
    }
    if (mode === "owner") {
      els.ownerView.classList.remove("hidden");
      renderOwnerCabinet();
      return;
    }
    if (mode === "dropper") {
      els.orderMain.classList.remove("hidden");
      els.mainTabs.classList.remove("hidden");
      els.cartChip.classList.remove("hidden");
      updateCartIndicators();
      return;
    }
    els.bootStatus.classList.remove("hidden");
    els.bootStatus.textContent = "Немає доступу до цієї Mini App у поточному чаті.";
  }

  async function bootstrapSession() {
    const unsafe = tg?.initDataUnsafe || {};
    sessionState.chat_id = unsafe.chat?.id != null ? String(unsafe.chat.id) : "";
    sessionState.user_id = unsafe.user?.id != null ? String(unsafe.user.id) : "";
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
      if (sessionState.role === "dropper") {
        showMode("dropper");
        return;
      }
      if (sessionState.need_registration) {
        showMode("register");
        return;
      }
      if (sessionState.role === "manager" || sessionState.role === "warehouse") {
        els.bootStatus.classList.remove("hidden");
        els.bootStatus.textContent = `Роль «${sessionState.role}». Кабінет співробітника — наступний етап.`;
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
        if (tg?.showAlert) {
          tg.showAlert("Реєстрацію успішно завершено. Можна відкривати /menu для замовлень.");
        }
        sessionState.role = "dropper";
        sessionState.need_registration = false;
        showMode("dropper");
      } catch (error) {
        els.registerError.textContent = error.message || "Помилка реєстрації";
        els.registerError.classList.remove("hidden");
      }
    });
  }

  if (els.staffForm) {
    els.staffForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      els.staffError.classList.add("hidden");
      const payload = {
        owner_chat_id: currentTelegramChatId(),
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
    els.ownerDroppers.addEventListener("change", async (event) => {
      const input = event.target.closest("[data-pay-flag]");
      if (!input) return;
      const chatId = input.getAttribute("data-pay-flag");
      try {
        const response = await fetch(
          `/api/owner/droppers/${encodeURIComponent(chatId)}/payment-flag`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              owner_chat_id: currentTelegramChatId(),
              require_full_payment: Boolean(input.checked),
            }),
          }
        );
        const data = await response.json();
        if (!response.ok) {
          throw new Error(typeof data.detail === "string" ? data.detail : "Помилка");
        }
        showToast("Налаштування збережено");
      } catch (error) {
        showToast(error.message || "Не вдалося зберегти");
        input.checked = !input.checked;
      }
    });
  }

  updateCartIndicators();
  bootstrapSession();
})();
