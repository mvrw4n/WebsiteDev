/**
 * Wizzy common utility functions
 */

const WizzyUtils = {
    /**
     * Format date to localized string
     * @param {string} dateString - ISO date string
     * @param {boolean} includeTime - Whether to include time
     * @returns {string} Formatted date string
     */
    formatDate: function (dateString, includeTime = true) {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return new Intl.DateTimeFormat('fr-FR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            ...(includeTime ? {
                hour: '2-digit',
                minute: '2-digit'
            } : {})
        }).format(date);
    },

    /**
     * Calculate price with volume discount
     * @param {number} leads - Number of leads
     * @returns {number} Price per lead
     */
    calculatePrice: function (leads) {
        const basePrice = 1.0;
        const minPrice = 0.3;
        const maxLeads = 30000;

        // Calculate degressive price
        const priceRange = basePrice - minPrice;
        const priceReduction = (leads / maxLeads) * priceRange;
        const currentPrice = basePrice - priceReduction;

        return Math.max(currentPrice, minPrice);
    },

    /**
     * Format currency amount
     * @param {number} amount - Amount to format
     * @param {string} currency - Currency code
     * @returns {string} Formatted currency string
     */
    formatCurrency: function (amount, currency = 'EUR') {
        return new Intl.NumberFormat('fr-FR', {
            style: 'currency',
            currency: currency
        }).format(amount);
    },

    /**
     * Get label for entity type
     * @param {string} entityType - Entity type key
     * @returns {string} Human-readable label
     */
    getEntityTypeLabel: function (entityType) {
        const labels = {
            'mairie': 'Mairie',
            'entreprise': 'Entreprise',
            'b2b_lead': 'B2B Lead',
            'custom': 'Structure personnalisée',
            'company': 'Entreprise',
            'person': 'Personne',
            'website': 'Site web',
            'social_profile': 'Profil social',
            'job_posting': 'Offre d\'emploi'
        };
        return labels[entityType] || entityType;
    },

    /**
     * Get human-readable label for job status
     * @param {string} status - Status key
     * @returns {string} Human-readable status
     */
    getJobStatusLabel: function (status) {
        const labels = {
            'pending': 'En attente',
            'running': 'En cours',
            'completed': 'Terminée',
            'failed': 'Échouée',
            'paused': 'En pause',
            'initializing': 'Initialisation',
            'crawling': 'Exploration',
            'extracting': 'Extraction de données',
            'processing': 'Traitement'
        };
        return labels[status] || status;
    },

    /**
     * Get color class for job status
     * @param {string} status - Status key
     * @returns {string} Bootstrap color class
     */
    getJobStatusColor: function (status) {
        const colors = {
            'pending': 'secondary',
            'running': 'primary',
            'initializing': 'info',
            'crawling': 'info',
            'extracting': 'info',
            'processing': 'primary',
            'completed': 'success',
            'failed': 'danger',
            'paused': 'warning'
        };
        return colors[status] || 'secondary';
    },

    /**
     * Make an authenticated API request
     * @param {string} url - API endpoint
     * @param {object} options - Fetch options
     * @returns {Promise} Fetch promise
     */
    apiRequest: async function (url, options = {}) {
        const token = localStorage.getItem('access_token');

        // Merge headers properly
        const headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        // Create new options object with merged headers
        const mergedOptions = {
            ...options,
            headers: headers
        };

        try {
            let response = await fetch(url, mergedOptions);

            // Handle 401 Unauthorized
            if (response.status === 401 && token) {
                // Token expired or invalid, try to refresh
                const refreshed = await this.refreshToken();
                if (refreshed) {
                    // Retry the request with new token
                    const newToken = localStorage.getItem('access_token');
                    mergedOptions.headers.Authorization = `Bearer ${newToken}`;
                    response = await fetch(url, mergedOptions);
                    return response;
                } else {
                    // If refresh failed, clear tokens
                    localStorage.removeItem('access_token');
                    localStorage.removeItem('refresh_token');

                    // Make an unauthenticated request if token refresh failed
                    delete mergedOptions.headers.Authorization;
                    return await fetch(url, mergedOptions);
                }
            }

            return response;
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    },

    /**
     * Refresh the JWT token
     * @returns {boolean} Whether refresh was successful
     */
    refreshToken: async function () {
        const refresh = localStorage.getItem('refresh_token');
        if (!refresh) {
            localStorage.removeItem('access_token');  // Clean up any stale access token
            return false;
        }

        try {
            const response = await fetch('/auth/jwt/refresh/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ refresh })
            });

            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('access_token', data.access);
                if (data.refresh) {  // If we get a new refresh token
                    localStorage.setItem('refresh_token', data.refresh);
                }
                return true;
            }

            // If refresh token is invalid, clean up
            if (response.status === 401) {
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
            }
            return false;
        } catch (error) {
            console.error('Token refresh failed:', error);
            return false;
        }
    },

    /**
     * Check if user is authenticated
     * @returns {boolean} Authentication status
     */
    isAuthenticated: function () {
        return !!localStorage.getItem('access_token');
    },

    /**
     * Get the JWT access token
     * @returns {string|null} The JWT token or null if not authenticated
     */
    getToken: function () {
        return localStorage.getItem('access_token');
    },

    /**
     * Show an alert/notification
     * @param {string} message - Message to display
     * @param {string} type - Alert type (success, danger, warning, info)
     * @param {string} containerId - ID of container element
     * @param {number} duration - Auto-hide duration in ms (0 for no auto-hide)
     */
    showAlert: function (message, type = 'info', containerId = 'alertsContainer', duration = 5000) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.setAttribute('role', 'alert');

        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

        container.appendChild(alertDiv);

        if (duration > 0) {
            setTimeout(() => {
                alertDiv.classList.remove('show');
                setTimeout(() => alertDiv.remove(), 150);
            }, duration);
        }
    },

    /**
     * Get human-readable time difference from now
     * @param {string} timestamp - ISO date string
     * @returns {string} Human-readable time difference
     */
    timeAgo: function (timestamp) {
        if (!timestamp) return '';

        const date = new Date(timestamp);
        const now = new Date();
        const secondsAgo = Math.floor((now - date) / 1000);

        if (isNaN(secondsAgo) || secondsAgo < 0) {
            return 'à l\'instant';
        }

        // Define time intervals
        const intervals = {
            année: 31536000,
            mois: 2592000,
            semaine: 604800,
            jour: 86400,
            heure: 3600,
            minute: 60,
            seconde: 1
        };

        // Format the time difference
        for (const [unit, seconds] of Object.entries(intervals)) {
            const interval = Math.floor(secondsAgo / seconds);

            if (interval >= 1) {
                // Handle plural forms for French
                if (unit === 'mois') {
                    return `il y a ${interval} ${unit}`;
                } else if (interval === 1) {
                    if (unit === 'année') return `il y a 1 an`;
                    if (unit === 'jour') return `il y a 1 jour`;
                    if (unit === 'heure') return `il y a 1 heure`;
                    if (unit === 'minute') return `il y a 1 minute`;
                    if (unit === 'seconde') return `il y a 1 seconde`;
                    return `il y a 1 ${unit}`;
                } else {
                    if (unit === 'année') return `il y a ${interval} ans`;
                    return `il y a ${interval} ${unit}s`;
                }
            }
        }

        return 'à l\'instant';
    }
};

// If using as a module
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WizzyUtils;
} 