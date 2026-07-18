(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  const CART_KEY = "kirs_cart_v1";

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
    npDeliveryFields: document.getElementById("npDeliveryFields"),
    ttnFields: document.getElementById("ttnFields"),
    warehouseField: document.getElementById("warehouseField"),
    addressField: document.getElementById("addressField"),
    warehouseLabel: document.getElementById("warehouseLabel"),
    prepayMaxLabel: document.getElementById("prepayMaxLabel"),
    prepay: document.getElementById("prepay"),
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
    syncDeliveryFields();
    syncTtnMode();
    updatePrepayHint();
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
    els.warehouseLabel.textContent = isCourier
      ? "Адреса доставки"
      : "Відділення/поштомат Нової Пошти";
  }

  function syncTtnMode() {
    const own = Boolean(els.ownTtn.checked);
    els.npDeliveryFields.classList.toggle("hidden", own);
    els.ttnFields.classList.toggle("hidden", !own);
  }

  function updatePrepayHint() {
    const max = Math.round(cartMoneyTotal());
    els.prepayMaxLabel.textContent = String(max);
    els.prepay.max = String(max);
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
    return {
      firstName: form.firstName.value.trim(),
      lastName: form.lastName.value.trim(),
      phone: form.phone.value.trim(),
      deliveryMethod,
      city: form.city.value.trim(),
      warehouse: form.warehouse.value.trim(),
      address: form.address.value.trim(),
      ownTtn: Boolean(form.ownTtn.checked),
      paymentMethod,
      prepay: form.prepay.value.trim(),
      comment: form.comment.value.trim(),
      rulesAccepted: Boolean(form.rulesAccepted.checked),
      cart: loadCart(),
      total: cartMoneyTotal(),
    };
  }

  function validateCheckout(data) {
    if (!data.firstName) return "Вкажіть ім'я отримувача";
    if (!data.lastName) return "Вкажіть прізвище отримувача";
    if (!data.phone || data.phone.replace(/\D/g, "").length < 10) {
      return "Вкажіть коректний телефон";
    }
    if (!data.ownTtn) {
      if (!data.city) return "Вкажіть населений пункт";
      if (data.deliveryMethod === "np_warehouse" && !data.warehouse) {
        return "Вкажіть відділення або поштомат";
      }
      if (data.deliveryMethod === "np_courier" && !data.address) {
        return "Вкажіть адресу доставки";
      }
    }
    if (!data.rulesAccepted) {
      return "Підтвердіть ознайомлення з правилами";
    }
    const prepay = data.prepay === "" ? 0 : Number(data.prepay);
    if (Number.isNaN(prepay) || prepay < 0) {
      return "Некоректна сума передплати";
    }
    if (prepay > data.total) {
      return `Передплата не може перевищувати ${Math.round(data.total)} грн`;
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

  els.checkoutForm.addEventListener("change", (event) => {
    if (event.target.name === "deliveryMethod") syncDeliveryFields();
    if (event.target.id === "ownTtn") syncTtnMode();
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
