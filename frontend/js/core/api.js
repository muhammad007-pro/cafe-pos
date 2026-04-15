// API Service - Backend bilan aloqa uchun
class API {
    constructor() {
        this.baseURL = 'http://localhost:8000/api/v1';
        this.token = localStorage.getItem('access_token');
        this.refreshToken = localStorage.getItem('refresh_token');
    }
    
    // Token olish
    getToken() {
        return this.token;
    }
    
    // Token yangilash
    setToken(token) {
        this.token = token;
        localStorage.setItem('access_token', token);
    }
    
    setRefreshToken(token) {
        this.refreshToken = token;
        localStorage.setItem('refresh_token', token);
    }
    
    // Tokenlarni tozalash
    clearTokens() {
        this.token = null;
        this.refreshToken = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
    }
    
    // Headers tayyorlash
    getHeaders() {
        const headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };
        
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        return headers;
    }
    
    // Token muddati tugagan bo'lsa yangilash
    async refreshAccessToken() {
        if (!this.refreshToken) {
            throw new Error('Refresh token mavjud emas');
        }
        
        try {
            const response = await fetch(`${this.baseURL}/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    refresh_token: this.refreshToken
                })
            });
            
            if (!response.ok) {
                throw new Error('Tokenni yangilab bo\'lmadi');
            }
            
            const data = await response.json();
            this.setToken(data.access_token);
            this.setRefreshToken(data.refresh_token);
            
            return data.access_token;
        } catch (error) {
            this.clearTokens();
            window.location.href = '/shared/login.html';
            throw error;
        }
    }
    
    // Asosiy request metodi
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        
        const config = {
            ...options,
            headers: {
                ...this.getHeaders(),
                ...options.headers
            }
        };
        
        // Body bo'lsa JSON stringify qilish
        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }
        
        try {
            let response = await fetch(url, config);
            
            // Token muddati tugagan bo'lsa
            if (response.status === 401 && this.refreshToken) {
                try {
                    await this.refreshAccessToken();
                    
                    // Qaytadan so'rov yuborish
                    config.headers = {
                        ...config.headers,
                        'Authorization': `Bearer ${this.token}`
                    };
                    
                    response = await fetch(url, config);
                } catch (refreshError) {
                    this.clearTokens();
                    window.location.href = '/shared/login.html';
                    throw refreshError;
                }
            }
            
            // Javobni qayta ishlash
            const contentType = response.headers.get('content-type');
            
            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || data.message || 'Xatolik yuz berdi');
                }
                
                return {
                    success: true,
                    data: data,
                    status: response.status
                };
            } else {
                if (!response.ok) {
                    throw new Error('Xatolik yuz berdi');
                }
                
                return {
                    success: true,
                    data: await response.text(),
                    status: response.status
                };
            }
        } catch (error) {
            console.error('API Error:', error);
            
            return {
                success: false,
                error: error.message,
                data: null
            };
        }
    }
    
    // GET so'rovi
    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        
        return this.request(url, {
            method: 'GET'
        });
    }
    
    // POST so'rovi
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: data
        });
    }
    
    // PUT so'rovi
    async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: data
        });
    }
    
    // PATCH so'rovi
    async patch(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PATCH',
            body: data
        });
    }
    
    // DELETE so'rovi
    async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE'
        });
    }
    
    // File upload
    async upload(endpoint, file, additionalData = {}) {
        const formData = new FormData();
        formData.append('file', file);
        
        Object.keys(additionalData).forEach(key => {
            formData.append(key, additionalData[key]);
        });
        
        return this.request(endpoint, {
            method: 'POST',
            headers: {
                // Content-Type o'rnatilmaydi, browser o'zi o'rnatadi
            },
            body: formData
        });
    }
    
    // Multiple file upload
    async uploadMultiple(endpoint, files, additionalData = {}) {
        const formData = new FormData();
        
        files.forEach((file, index) => {
            formData.append(`files[${index}]`, file);
        });
        
        Object.keys(additionalData).forEach(key => {
            formData.append(key, additionalData[key]);
        });
        
        return this.request(endpoint, {
            method: 'POST',
            headers: {},
            body: formData
        });
    }
    
    // Download file
    async download(endpoint, filename) {
        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, {
                method: 'GET',
                headers: this.getHeaders()
            });
            
            if (!response.ok) {
                throw new Error('Faylni yuklab bo\'lmadi');
            }
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename || 'download';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            return { success: true };
        } catch (error) {
            console.error('Download error:', error);
            return { success: false, error: error.message };
        }
    }
}

export { API };