import { API } from '../core/api.js';
import { AuthService } from '../core/auth.js';
import { WebSocketManager } from '../core/socket.js';
import { StateManager } from '../core/state.js';
import { showToast } from '../ui/toast.js';
import { Modal } from '../ui/modal.js';
import { formatMoney, formatDuration } from '../utils/formatter.js';
import { debounce, generateOrderNumber } from '../utils/helpers.js';

class POSModule {
    constructor() {
        this.api = new API();
        this.auth = new AuthService();
        this.ws = new WebSocketManager();
        this.state = new StateManager();
        
        this.currentTable = null;
        this.currentOrder = null;
        this.cart = [];
        this.categories = [];
        this.products = [];
        this.tables = [];
        this.customers = [];
        
        this.modals = {
            table: new Modal('tableModal'),
            payment: new Modal('paymentModal'),
            customer: new Modal('customerModal'),
            discount: new Modal('discountModal')
        };
        
        this.init();
    }
    
    async init() {
        this.setupEventListeners();
        this.setupKeyboardShortcuts();
        await this.loadInitialData();
        this.setupWebSocket();
        this.hideLoadingScreen();
        this.renderCategories();
        this.renderProducts();
        this.updateUI();
    }
    
    setupEventListeners() {
        // Sidebar
        document.getElementById('sidebarCollapse')?.addEventListener('click', () => this.toggleSidebar());
        document.getElementById('mobileMenuToggle')?.addEventListener('click', () => this.toggleMobileMenu());
        
        // Theme
        document.getElementById('themeToggle')?.addEventListener('click', () => this.toggleTheme());
        
        // Fullscreen
        document.getElementById('fullscreenBtn')?.addEventListener('click', () => this.toggleFullscreen());
        
        // Search
        const searchInput = document.getElementById('searchProducts');
        searchInput?.addEventListener('input', debounce((e) => this.searchProducts(e.target.value), 300));
        
        // Table selection
        document.getElementById('changeTableBtn')?.addEventListener('click', () => this.openTableModal());
        
        // Customer
        document.getElementById('selectCustomerBtn')?.addEventListener('click', () => this.openCustomerModal());
        
        // Order type
        document.querySelectorAll('.order-type-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.setOrderType(e.target.dataset.type));
        });
        
        // Cart actions
        document.getElementById('clearCartBtn')?.addEventListener('click', () => this.clearCart());
        document.getElementById('holdOrderBtn')?.addEventListener('click', () => this.holdOrder());
        document.getElementById('checkoutBtn')?.addEventListener('click', () => this.openPaymentModal());
        
        // Quick actions
        document.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleQuickAction(btn.dataset.action));
        });
        
        // Payment modal
        document.querySelectorAll('.payment-method').forEach(btn => {
            btn.addEventListener('click', () => this.selectPaymentMethod(btn.dataset.method));
        });
        
        document.getElementById('cashReceived')?.addEventListener('input', (e) => this.calculateChange(e.target.value));
        document.querySelectorAll('.cash-btn').forEach(btn => {
            btn.addEventListener('click', () => this.setCashAmount(btn.dataset.amount));
        });
        
        document.getElementById('processPaymentBtn')?.addEventListener('click', () => this.processPayment());
        
        // Discount modal
        document.querySelectorAll('.discount-type-btn').forEach(btn => {
            btn.addEventListener('click', () => this.setDiscountType(btn.dataset.type));
        });
        
        document.querySelectorAll('.preset-btn').forEach(btn => {
            btn.addEventListener('click', () => this.setDiscountPreset(btn.dataset.value));
        });
        
        document.getElementById('applyDiscountBtn')?.addEventListener('click', () => this.applyDiscount());
        
        // Customer modal
        document.getElementById('customerSearch')?.addEventListener('input', debounce((e) => this.searchCustomers(e.target.value), 300));
        document.getElementById('addCustomerBtn')?.addEventListener('click', () => this.showAddCustomerForm());
        
        // Sort products
        document.getElementById('sortProducts')?.addEventListener('change', (e) => this.sortProducts(e.target.value));
        
        // Logout
        document.getElementById('logoutBtn')?.addEventListener('click', () => this.logout());
    }
    
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K - Focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                document.getElementById('searchProducts')?.focus();
            }
            
            // F2 - Open table modal
            if (e.key === 'F2') {
                e.preventDefault();
                this.openTableModal();
            }
            
            // F3 - Open customer modal
            if (e.key === 'F3') {
                e.preventDefault();
                this.openCustomerModal();
            }
            
            // F4 - Open discount modal
            if (e.key === 'F4' && this.cart.length > 0) {
                e.preventDefault();
                this.modals.discount.open();
            }
            
            // F5 - Hold order
            if (e.key === 'F5' && this.cart.length > 0) {
                e.preventDefault();
                this.holdOrder();
            }
            
            // F9 - Checkout
            if (e.key === 'F9' && this.cart.length > 0) {
                e.preventDefault();
                this.openPaymentModal();
            }
            
            // Esc - Close modals
            if (e.key === 'Escape') {
                Object.values(this.modals).forEach(modal => modal.close());
            }
        });
    }
    
    async loadInitialData() {
        try {
            this.updateLoadingProgress(20);
            
            const [categoriesRes, productsRes, tablesRes, customersRes] = await Promise.all([
                this.api.get('/categories/all'),
                this.api.get('/products/all'),
                this.api.get('/tables/all'),
                this.api.get('/customers/all')
            ]);
            
            this.categories = categoriesRes.data || [];
            this.products = productsRes.data || [];
            this.tables = tablesRes.data || [];
            this.customers = customersRes.data || [];
            
            this.updateLoadingProgress(80);
            
            // Set default table
            const freeTable = this.tables.find(t => t.status === 'free');
            if (freeTable) {
                this.selectTable(freeTable);
            }
            
            this.updateLoadingProgress(100);
            
        } catch (error) {
            showToast('Ma\'lumotlarni yuklashda xatolik', 'error');
            console.error('Failed to load initial data:', error);
        }
    }
    
    setupWebSocket() {
        this.ws.connect();
        
        this.ws.on('connected', () => {
            console.log('WebSocket connected to POS');
            this.ws.send({ type: 'join_room', room: 'pos' });
        });
        
        this.ws.on('order_updated', (data) => {
            if (this.currentOrder && data.order_id === this.currentOrder.id) {
                this.updateOrderStatus(data.status);
            }
        });
        
        this.ws.on('table_status_changed', (data) => {
            this.updateTableStatus(data.table_id, data.status);
        });
        
        this.ws.on('new_notification', (data) => {
            this.updateNotificationBadge(data.count);
            showToast(data.message, 'info');
        });
        
        this.ws.on('order_ready', (data) => {
            showToast(`Buyurtma #${data.order_number} tayyor!`, 'success', 5000);
            this.playNotificationSound();
        });
    }
    
    playNotificationSound() {
        const audio = new Audio('../assets/sounds/notification.mp3');
        audio.play().catch(e => console.log('Ovoz o\'chirilgan'));
    }
    
    updateOrderStatus(status) {
        const statusElement = document.querySelector('.order-status');
        if (statusElement) {
            statusElement.textContent = this.getStatusText(status);
            statusElement.className = `order-status ${status}`;
        }
    }
    
    updateTableStatus(tableId, status) {
        const table = this.tables.find(t => t.id === tableId);
        if (table) {
            table.status = status;
        }
        
        if (this.currentTable && this.currentTable.id === tableId) {
            this.currentTable.status = status;
        }
    }
    
    getStatusText(status) {
        const texts = {
            'pending': 'Kutilmoqda',
            'confirmed': 'Tasdiqlangan',
            'preparing': 'Tayyorlanmoqda',
            'ready': 'Tayyor',
            'served': 'Xizmat qilingan',
            'completed': 'Yakunlangan',
            'cancelled': 'Bekor qilingan'
        };
        return texts[status] || status;
    }
    
    hideLoadingScreen() {
        const loadingScreen = document.getElementById('loadingScreen');
        loadingScreen?.classList.add('hidden');
    }
    
    updateLoadingProgress(percent) {
        const progressBar = document.getElementById('loadingProgress');
        if (progressBar) {
            progressBar.style.width = `${percent}%`;
        }
    }
    
    renderCategories() {
        const container = document.getElementById('categoriesList');
        if (!container) return;
        
        container.innerHTML = '';
        
        const allCategory = document.createElement('button');
        allCategory.className = 'category-item active';
        allCategory.textContent = 'Barchasi';
        allCategory.addEventListener('click', () => this.filterByCategory(null));
        container.appendChild(allCategory);
        
        this.categories.forEach(category => {
            const btn = document.createElement('button');
            btn.className = 'category-item';
            btn.textContent = category.name;
            btn.addEventListener('click', () => this.filterByCategory(category.id));
            container.appendChild(btn);
        });
    }
    
    renderProducts(categoryId = null) {
        const container = document.getElementById('productsGrid');
        if (!container) return;
        
        let filteredProducts = this.products;
        if (categoryId) {
            filteredProducts = this.products.filter(p => p.category_id === categoryId);
        }
        
        container.innerHTML = '';
        
        filteredProducts.forEach(product => {
            const card = this.createProductCard(product);
            container.appendChild(card);
        });
        
        const categoryTitle = document.getElementById('currentCategory');
        if (categoryTitle) {
            if (categoryId) {
                const category = this.categories.find(c => c.id === categoryId);
                categoryTitle.textContent = category?.name || 'Mahsulotlar';
            } else {
                categoryTitle.textContent = 'Barcha mahsulotlar';
            }
        }
    }
    
    createProductCard(product) {
        const card = document.createElement('div');
        card.className = `product-card ${!product.is_available ? 'unavailable' : ''}`;
        card.dataset.id = product.id;
        card.dataset.price = product.price;
        
        card.innerHTML = `
            <img src="${product.image_url || '../assets/images/product-placeholder.jpg'}" 
                 alt="${product.name}" 
                 class="product-image"
                 loading="lazy">
            <div class="product-info">
                <h4 class="product-name">${product.name}</h4>
                <div class="product-price">${formatMoney(product.price)}</div>
            </div>
            ${!product.is_available ? '<span class="product-badge">Mavjud emas</span>' : ''}
        `;
        
        if (product.is_available) {
            card.addEventListener('click', () => this.addToCart(product));
        }
        
        return card;
    }
    
    filterByCategory(categoryId) {
        document.querySelectorAll('.category-item').forEach((btn, index) => {
            btn.classList.toggle('active', index === 0 ? !categoryId : false);
        });
        
        this.renderProducts(categoryId);
    }
    
    addToCart(product, quantity = 1, notes = '') {
        const existingItem = this.cart.find(item => item.product_id === product.id);
        
        if (existingItem) {
            existingItem.quantity += quantity;
            existingItem.total_price = existingItem.unit_price * existingItem.quantity;
        } else {
            this.cart.push({
                product_id: product.id,
                product_name: product.name,
                quantity: quantity,
                unit_price: product.price,
                total_price: product.price * quantity,
                notes: notes
            });
        }
        
        this.updateCart();
        showToast(`${product.name} qo'shildi`, 'success');
        
        if (window.navigator.vibrate) {
            window.navigator.vibrate(50);
        }
    }
    
    updateCart() {
        this.renderCartItems();
        this.updateCartTotals();
        this.updateCheckoutButton();
    }
    
    renderCartItems() {
        const container = document.getElementById('cartItems');
        const emptyState = document.getElementById('cartEmpty');
        
        if (!container) return;
        
        if (this.cart.length === 0) {
            container.innerHTML = '';
            if (emptyState) container.appendChild(emptyState);
            return;
        }
        
        container.innerHTML = '';
        
        this.cart.forEach((item, index) => {
            const cartItem = this.createCartItem(item, index);
            container.appendChild(cartItem);
        });
    }
    
    createCartItem(item, index) {
        const div = document.createElement('div');
        div.className = 'cart-item';
        div.dataset.index = index;
        
        div.innerHTML = `
            <div class="cart-item-info">
                <div class="cart-item-name">${item.product_name}</div>
                <div class="cart-item-price">${formatMoney(item.unit_price)}</div>
                ${item.notes ? `<small class="cart-item-notes">${item.notes}</small>` : ''}
            </div>
            <div class="cart-item-controls">
                <div class="cart-item-qty">
                    <button class="qty-btn decrease">-</button>
                    <span>${item.quantity}</span>
                    <button class="qty-btn increase">+</button>
                </div>
                <div class="cart-item-total">${formatMoney(item.total_price)}</div>
                <button class="cart-item-remove btn-icon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                        <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </button>
            </div>
        `;
        
        div.querySelector('.decrease').addEventListener('click', () => this.updateItemQuantity(index, -1));
        div.querySelector('.increase').addEventListener('click', () => this.updateItemQuantity(index, 1));
        div.querySelector('.cart-item-remove').addEventListener('click', () => this.removeFromCart(index));
        
        return div;
    }
    
    updateItemQuantity(index, delta) {
        const item = this.cart[index];
        const newQuantity = item.quantity + delta;
        
        if (newQuantity <= 0) {
            this.removeFromCart(index);
        } else {
            item.quantity = newQuantity;
            item.total_price = item.unit_price * newQuantity;
            this.updateCart();
        }
    }
    
    removeFromCart(index) {
        const item = this.cart[index];
        this.cart.splice(index, 1);
        this.updateCart();
        showToast(`${item.product_name} o'chirildi`, 'info');
    }
    
    clearCart() {
        if (this.cart.length === 0) return;
        
        if (confirm('Savatchani tozalashni xohlaysizmi?')) {
            this.cart = [];
            this.updateCart();
            showToast('Savatcha tozalandi', 'info');
        }
    }
    
    updateCartTotals() {
        const subtotal = this.cart.reduce((sum, item) => sum + item.total_price, 0);
        const discount = this.state.get('discount') || 0;
        const tax = (subtotal - discount) * 0.12;
        const service = (subtotal - discount) * 0.10;
        const total = subtotal - discount + tax + service;
        
        document.getElementById('cartSubtotal').textContent = formatMoney(subtotal);
        document.getElementById('cartDiscount').textContent = `-${formatMoney(discount)}`;
        document.getElementById('cartTax').textContent = formatMoney(tax);
        document.getElementById('cartService').textContent = formatMoney(service);
        document.getElementById('cartTotal').textContent = formatMoney(total);
        
        this.state.set('cartTotals', { subtotal, discount, tax, service, total });
    }
    
    updateCheckoutButton() {
        const checkoutBtn = document.getElementById('checkoutBtn');
        if (checkoutBtn) {
            checkoutBtn.disabled = this.cart.length === 0 || !this.currentTable;
        }
    }
    
    async openTableModal() {
        await this.renderFloorPlan();
        this.modals.table.open();
    }
    
    async renderFloorPlan() {
        const container = document.getElementById('floorPlan');
        if (!container) return;
        
        container.innerHTML = '';
        
        const sections = {};
        this.tables.forEach(table => {
            if (!sections[table.section]) {
                sections[table.section] = [];
            }
            sections[table.section].push(table);
        });
        
        Object.entries(sections).forEach(([section, tables]) => {
            const sectionDiv = document.createElement('div');
            sectionDiv.className = 'floor-section';
            sectionDiv.innerHTML = `<h4 class="section-title">${section || 'Asosiy zal'}</h4>`;
            
            const tablesGrid = document.createElement('div');
            tablesGrid.className = 'tables-grid';
            
            tables.forEach(table => {
                const tableCard = this.createTableCard(table);
                tablesGrid.appendChild(tableCard);
            });
            
            sectionDiv.appendChild(tablesGrid);
            container.appendChild(sectionDiv);
        });
    }
    
    createTableCard(table) {
        const card = document.createElement('div');
        card.className = `table-card ${table.status}`;
        card.dataset.id = table.id;
        
        card.innerHTML = `
            <div class="table-number">${table.number}</div>
            <div class="table-capacity">${table.capacity} kishi</div>
            <div class="table-status"></div>
            ${table.order ? `<div class="table-order">#${table.order.order_number}</div>` : ''}
        `;
        
        card.addEventListener('click', () => this.selectTable(table));
        
        return card;
    }
    
    async selectTable(table) {
        this.currentTable = table;
        
        document.getElementById('currentTableDisplay').textContent = `Stol #${table.number}`;
        
        if (table.order) {
            this.currentOrder = table.order;
            this.cart = table.order.items.map(item => ({
                product_id: item.product_id,
                product_name: item.product_name,
                quantity: item.quantity,
                unit_price: item.unit_price,
                total_price: item.total_price,
                notes: item.notes
            }));
            this.updateCart();
        } else {
            this.currentOrder = null;
        }
        
        this.modals.table.close();
        this.updateCheckoutButton();
        showToast(`Stol #${table.number} tanlandi`, 'success');
    }
    
    setOrderType(type) {
        this.state.set('orderType', type);
        
        document.querySelectorAll('.order-type-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.type === type);
        });
    }
    
    async openCustomerModal() {
        await this.renderCustomersList();
        this.modals.customer.open();
    }
    
    renderCustomersList(customers = null) {
        const container = document.getElementById('customersList');
        if (!container) return;
        
        const displayCustomers = customers || this.customers;
        
        container.innerHTML = '';
        
        displayCustomers.forEach(customer => {
            const card = this.createCustomerCard(customer);
            container.appendChild(card);
        });
    }
    
    createCustomerCard(customer) {
        const card = document.createElement('div');
        card.className = 'customer-card';
        
        const initials = customer.name.split(' ').map(n => n[0]).join('').toUpperCase();
        
        card.innerHTML = `
            <div class="customer-avatar">${initials}</div>
            <div class="customer-info">
                <div class="customer-name">${customer.name}</div>
                <div class="customer-phone">${customer.phone || 'Telefon yo\'q'}</div>
            </div>
            <div class="customer-points">
                <div class="points-value">${customer.points}</div>
                <div class="points-label">ball</div>
            </div>
        `;
        
        card.addEventListener('click', () => this.selectCustomer(customer));
        
        return card;
    }
    
    selectCustomer(customer) {
        this.state.set('selectedCustomer', customer);
        document.getElementById('selectedCustomerName').textContent = customer.name;
        this.modals.customer.close();
        showToast(`${customer.name} tanlandi`, 'success');
    }
    
    async searchCustomers(query) {
        if (!query) {
            this.renderCustomersList();
            return;
        }
        
        try {
            const response = await this.api.get('/customers/search', { query });
            this.renderCustomersList(response.data);
        } catch (error) {
            console.error('Failed to search customers:', error);
        }
    }
    
    searchProducts(query) {
        if (!query) {
            this.renderProducts();
            return;
        }
        
        const filtered = this.products.filter(p => 
            p.name.toLowerCase().includes(query.toLowerCase()) ||
            p.barcode?.includes(query)
        );
        
        const container = document.getElementById('productsGrid');
        container.innerHTML = '';
        
        filtered.forEach(product => {
            const card = this.createProductCard(product);
            container.appendChild(card);
        });
    }
    
    sortProducts(type) {
        let sorted = [...this.products];
        
        switch(type) {
            case 'popular':
                sorted.sort((a, b) => (b.order_count || 0) - (a.order_count || 0));
                break;
            case 'price_asc':
                sorted.sort((a, b) => a.price - b.price);
                break;
            case 'price_desc':
                sorted.sort((a, b) => b.price - a.price);
                break;
            case 'name':
                sorted.sort((a, b) => a.name.localeCompare(b.name));
                break;
        }
        
        this.products = sorted;
        this.renderProducts();
    }
    
    handleQuickAction(action) {
        switch(action) {
            case 'discount':
                if (this.cart.length > 0) {
                    this.modals.discount.open();
                } else {
                    showToast('Savatcha bo\'sh', 'warning');
                }
                break;
            case 'notes':
                this.showNotesInput();
                break;
            case 'split':
                this.splitOrder();
                break;
            case 'print':
                this.printOrder();
                break;
        }
    }
    
    showNotesInput() {
        const notes = prompt('Buyurtma uchun izoh kiriting:');
        if (notes !== null) {
            this.state.set('orderNotes', notes);
            showToast('Izoh saqlandi', 'success');
        }
    }
    
    async splitOrder() {
        if (this.cart.length < 2) {
            showToast('Bo\'lish uchun kamida 2 ta mahsulot kerak', 'warning');
            return;
        }
        showToast('Buyurtmani bo\'lish tez orada...', 'info');
    }
    
    async printOrder() {
        if (this.cart.length === 0) {
            showToast('Savatcha bo\'sh', 'warning');
            return;
        }
        
        try {
            await this.api.post('/printer/order', {
                items: this.cart,
                table: this.currentTable
            });
            showToast('Chop etish boshlandi', 'info');
        } catch (error) {
            showToast('Chop etishda xatolik', 'error');
        }
    }
    
    setDiscountType(type) {
        this.state.set('discountType', type);
        
        const unit = document.getElementById('discountUnit');
        if (unit) {
            unit.textContent = type === 'percentage' ? '%' : 'UZS';
        }
        
        document.querySelectorAll('.discount-type-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.type === type);
        });
    }
    
    setDiscountPreset(value) {
        document.getElementById('discountValue').value = value;
    }
    
    applyDiscount() {
        const type = this.state.get('discountType') || 'percentage';
        const value = parseFloat(document.getElementById('discountValue').value);
        const subtotal = this.cart.reduce((sum, item) => sum + item.total_price, 0);
        
        let discountAmount = 0;
        
        if (type === 'percentage') {
            discountAmount = subtotal * (value / 100);
        } else {
            discountAmount = Math.min(value, subtotal);
        }
        
        this.state.set('discount', discountAmount);
        this.updateCartTotals();
        this.modals.discount.close();
        
        showToast(`Chegirma qo'llandi: ${formatMoney(discountAmount)}`, 'success');
    }
    
    async holdOrder() {
        if (this.cart.length === 0) return;
        
        try {
            const orderData = {
                table_id: this.currentTable?.id,
                items: this.cart,
                notes: this.state.get('orderNotes') || '',
                order_type: this.state.get('orderType') || 'dine-in',
                customer_id: this.state.get('selectedCustomer')?.id
            };
            
            await this.api.post('/orders/hold', orderData);
            
            showToast('Buyurtma saqlandi', 'success');
            this.clearCart();
            
        } catch (error) {
            showToast('Buyurtmani saqlashda xatolik', 'error');
        }
    }
    
    openPaymentModal() {
        if (this.cart.length === 0) {
            showToast('Savatcha bo\'sh', 'warning');
            return;
        }
        
        if (!this.currentTable) {
            showToast('Iltimos, stol tanlang', 'warning');
            return;
        }
        
        const totals = this.state.get('cartTotals');
        document.getElementById('paymentTotalAmount').textContent = formatMoney(totals.total);
        
        this.modals.payment.open();
    }
    
    selectPaymentMethod(method) {
        this.state.set('paymentMethod', method);
        
        document.querySelectorAll('.payment-method').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.method === method);
        });
        
        const cashSection = document.getElementById('cashPaymentSection');
        if (cashSection) {
            cashSection.style.display = method === 'cash' ? 'block' : 'none';
        }
    }
    
    setCashAmount(amount) {
        const input = document.getElementById('cashReceived');
        const totals = this.state.get('cartTotals');
        
        if (amount === 'exact') {
            input.value = totals.total;
        } else {
            input.value = parseInt(amount);
        }
        
        this.calculateChange(input.value);
    }
    
    calculateChange(received) {
        const totals = this.state.get('cartTotals');
        const change = Math.max(0, parseFloat(received) - totals.total);
        
        document.getElementById('changeAmount').textContent = formatMoney(change);
    }
    
    async processPayment() {
        const method = this.state.get('paymentMethod') || 'cash';
        const totals = this.state.get('cartTotals');
        
        try {
            const btn = document.getElementById('processPaymentBtn');
            btn.classList.add('loading');
            btn.disabled = true;
            
            const orderData = {
                table_id: this.currentTable.id,
                items: this.cart,
                notes: this.state.get('orderNotes') || '',
                order_type: this.state.get('orderType') || 'dine-in',
                customer_id: this.state.get('selectedCustomer')?.id,
                discount: totals.discount
            };
            
            const orderResponse = await this.api.post('/orders', orderData);
            const order = orderResponse.data;
            
            const paymentData = {
                order_id: order.id,
                amount: totals.total,
                method: method,
                cash_received: method === 'cash' ? parseFloat(document.getElementById('cashReceived').value) : null
            };
            
            await this.api.post('/payments', paymentData);
            
            this.cart = [];
            this.updateCart();
            this.modals.payment.close();
            
            showToast('To\'lov muvaffaqiyatli amalga oshirildi', 'success');
            
            this.state.clear();
            
            await this.checkTableOrders();
            
        } catch (error) {
            showToast('To\'lovni amalga oshirishda xatolik', 'error');
            console.error('Payment error:', error);
        } finally {
            const btn = document.getElementById('processPaymentBtn');
            btn.classList.remove('loading');
            btn.disabled = false;
        }
    }
    
    async checkTableOrders() {
        if (!this.currentTable) return;
        
        try {
            const response = await this.api.get(`/tables/${this.currentTable.id}/orders`);
            const activeOrders = response.data.filter(o => o.status !== 'completed' && o.status !== 'cancelled');
            
            if (activeOrders.length === 0) {
                await this.api.post(`/tables/${this.currentTable.id}/free`);
                this.currentTable.status = 'free';
                
                const freeTable = this.tables.find(t => t.status === 'free');
                if (freeTable) {
                    this.selectTable(freeTable);
                }
            }
        } catch (error) {
            console.error('Failed to check table orders:', error);
        }
    }
    
    async showAddCustomerForm() {
        showToast('Yangi mijoz qo\'shish tez orada...', 'info');
    }
    
    toggleSidebar() {
        document.getElementById('sidebar')?.classList.toggle('collapsed');
    }
    
    toggleMobileMenu() {
        document.getElementById('sidebar')?.classList.toggle('open');
    }
    
    toggleTheme() {
        const html = document.documentElement;
        const currentTheme = html.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        html.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        
        const sunIcon = document.querySelector('.sun-icon');
        const moonIcon = document.querySelector('.moon-icon');
        if (sunIcon && moonIcon) {
            sunIcon.style.display = newTheme === 'dark' ? 'none' : 'block';
            moonIcon.style.display = newTheme === 'dark' ? 'block' : 'none';
        }
    }
    
    toggleFullscreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    }
    
    updateNotificationBadge(count) {
        const badge = document.querySelector('.notification-badge');
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'flex' : 'none';
        }
    }
    
    async loadNotificationCount() {
        try {
            const response = await this.api.get('/notifications/unread/count');
            this.updateNotificationBadge(response.data.count);
        } catch (error) {
            console.error('Failed to load notification count:', error);
        }
    }
    
    updateUI() {
        const user = this.auth.getCurrentUser();
        if (user) {
            document.querySelector('.user-name').textContent = user.full_name;
            document.querySelector('.user-role').textContent = user.role;
        }
        
        const savedTheme = localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        
        this.loadNotificationCount();
    }
    
    async logout() {
        if (confirm('Tizimdan chiqishni xohlaysizmi?')) {
            this.ws.disconnect();
            await this.auth.logout();
            window.location.href = '../shared/login.html';
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.pos = new POSModule();
});

export default POSModule;