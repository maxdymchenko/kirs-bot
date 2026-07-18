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
    ownTtn: document.getElementById("ownTtn"),
    ttnFields: document.getElementById("ttnFields"),
    ttnNumber: document.getElementById("ttnNumber"),
    warehouseField: document.getElementById("warehouseField"),
    addressField: document.getElementById("addressField"),
    warehouseLabel: document.getElementById("warehouseLabel"),
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

  const PHONE_EXAMPLE = "+38(099)999-99-99";
  const PHONE_MAX_DIGITS = 12;

  const npState = {
    city: null,
    warehouse: null,
    cityTimer: null,
    warehouseTimer: null,
    cityReq: 0,
    warehouseReq: 0,
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

  function normalizePhoneDigits(raw) {
    let digits = String(raw || "").replace(/\D/g, "");
    if (!digits) return "";

    if (digits.startsWith("380")) {
      return digits.slice(0, PHONE_MAX_DIGITS);
    }
    if (digits.startsWith("38")) {
      return digits.slice(0, PHONE_MAX_DIGITS);
    }
    if (digits.startsWith("0")) {
      return ("38" + digits).slice(0, PHONE_MAX_DIGITS);
    }
    // 67xxxxxxx / 9 цифр без нуля
    return ("380" + digits).slice(0, PHONE_MAX_DIGITS);
  }

  function formatPhonePartial(digits) {
    if (!digits) return "";

    let result = "";
    if (digits.length >= 1) result = "+" + digits.slice(0, Math.min(2, digits.length));
    if (digits.length >= 2) result = "+38";
    if (digits.length > 2) {
      result += "(" + digits.slice(2, Math.min(5, digits.length));
      if (digits.length >= 5) {
        result += ")";
        if (digits.length > 5) {
          result += digits.slice(5, Math.min(8, digits.length));
          if (digits.length >= 8) {
            result += "-" + digits.slice(8, Math.min(10, digits.length));
            if (digits.length >= 10) {
              result += "-" + digits.slice(10, Math.min(12, digits.length));
            }
          }
        }
      }
    }
    return result;
  }

  function applyPhoneMask(rawValue) {
    const digits = normalizePhoneDigits(rawValue);
    const formatted = formatPhonePartial(digits);
    els.phone.value = formatted;
    if (els.phoneGhost) {
      els.phoneGhost.textContent = PHONE_EXAMPLE;
      els.phoneGhost.classList.toggle("hidden", false);
    }
    return { digits, formatted };
  }

  function isPhoneComplete(value) {
    return normalizePhoneDigits(value).length === PHONE_MAX_DIGITS;
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

  function openCheckout() {
    const cart = loadCart();
    if (!cart.length) return;
    els.catalogView.classList.add("hidden");
    els.cartView.classList.add("hidden");
    els.checkoutView.classList.remove("hidden");
    els.mainTabs.classList.add("hidden");
    document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
    renderRequisitesDetails();
    syncDeliveryFields();
    syncPaymentAndTtn();
    setCheckoutError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function syncDeliveryFields() {
    const method =
      els.checkoutForm.querySelector('input[name="deliveryMethod"]:checked')?.value ||
      "np_warehouse";
    const isCourier = method === "np_courier";
    els.warehouseField.classList.toggle("hidden", isCourier);
    els.addressField.classList.toggle("hidden", !isCourier);
    if (!isCourier) {
      els.warehouseLabel.textContent = "Відділення/поштомат Нової Пошти";
    }
    syncWarehouseEnabled();
  }

  function syncWarehouseEnabled() {
    const hasCity = Boolean(npState.city?.city_ref);
    els.warehouse.disabled = !hasCity;
    if (!hasCity) {
      clearWarehouseSelection({ keepText: false });
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
    syncWarehouseEnabled();
  }

  function clearWarehouseSelection({ keepText = true } = {}) {
    npState.warehouse = null;
    els.warehouseRef.value = "";
    if (!keepText) els.warehouse.value = "";
    markSelected(els.warehouse, false);
    hideDropdown(els.warehouseDropdown);
  }

  function selectCity(item) {
    npState.city = item;
    els.city.value = item.label || item.present || item.main_description || "";
    els.cityRef.value = item.city_ref || "";
    els.settlementRef.value = item.settlement_ref || "";
    markSelected(els.city, true);
    hideDropdown(els.cityDropdown);
    clearWarehouseSelection({ keepText: false });
    syncWarehouseEnabled();
    els.warehouse.focus();
  }

  function selectWarehouse(item) {
    npState.warehouse = item;
    els.warehouse.value = item.label || item.description || "";
    els.warehouseRef.value = item.ref || "";
    markSelected(els.warehouse, true);
    hideDropdown(els.warehouseDropdown);
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

    els.prepayBlock.classList.toggle("hidden", !showPrepay);
    els.requisitesBlock.classList.toggle("hidden", !showRequisites);
    els.ttnPdfField.classList.toggle("hidden", !ownTtn);

    const total = Math.round(cartMoneyTotal());
    els.prepayMaxLabel.textContent = String(total);
    els.prepay.max = String(total);
    els.payAmountLabel.textContent = `${total} грн`;
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
      lastName: form.lastName.value.trim(),
      phone: form.phone.value.trim(),
      deliveryMethod,
      city: form.city.value.trim(),
      cityRef: form.cityRef.value.trim(),
      settlementRef: form.settlementRef.value.trim(),
      warehouse: form.warehouse.value.trim(),
      warehouseRef: form.warehouseRef.value.trim(),
      address: form.address.value.trim(),
      npCity: npState.city,
      npWarehouse: npState.warehouse,
      ownTtn: Boolean(form.ownTtn.checked),
      ttnNumber: form.ttnNumber?.value.trim() || "",
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
    if (!data.phone || !isPhoneComplete(data.phone)) {
      return "Вкажіть повний телефон у форматі +38(0XX)XXX-XX-XX";
    }
    if (!data.cityRef || !npState.city) {
      return "Оберіть населений пункт зі списку Нової Пошти";
    }
    if (data.deliveryMethod === "np_warehouse" && (!data.warehouseRef || !npState.warehouse)) {
      return "Оберіть відділення/поштомат зі списку Нової Пошти";
    }
    if (data.deliveryMethod === "np_courier" && !data.address) {
      return "Вкажіть адресу доставки";
    }
    if (data.ownTtn) {
      if (!data.ttnNumber) return "Вкажіть номер ТТН";
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
    if (data.paymentMethod === "requisites" && !data.receiptFile) {
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

  els.phone.addEventListener("input", () => {
    const { formatted } = applyPhoneMask(els.phone.value);
    const pos = formatted.length;
    try {
      els.phone.setSelectionRange(pos, pos);
    } catch {
      /* ignore */
    }
  });

  els.phone.addEventListener("paste", (event) => {
    event.preventDefault();
    const text = event.clipboardData?.getData("text") || "";
    const { formatted } = applyPhoneMask(text);
    const pos = formatted.length;
    try {
      els.phone.setSelectionRange(pos, pos);
    } catch {
      /* ignore */
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

  document.addEventListener("click", (event) => {
    if (!event.target.closest('[data-ac="city"]')) {
      hideDropdown(els.cityDropdown);
    }
    if (!event.target.closest('[data-ac="warehouse"]')) {
      hideDropdown(els.warehouseDropdown);
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

  updateCartIndicators();
})();
