// Add a debug flag to bypass token checks
const DEBUG_MODE = true;

// Override fetch to check authentication
const originalFetch = window.fetch;
window.fetch = function () {
    const url = arguments[0];
    const options = arguments[1] || {};

    // Skip token check for debugging or for specific endpoints
    const skipAuth = DEBUG_MODE ||
        url.includes('/api/scraping/jobs/') ||
        url.includes('/auth/login/') ||
        url.includes('/static/');

    // Only check authentication for API calls
    if (url.includes('/api/') && !skipAuth) {
        const token = localStorage.getItem('token') || sessionStorage.getItem('token');

        if (!token) {
            console.warn(`Unauthenticated API call: ${url}`);

            // For debugging, allow the call to proceed
            if (DEBUG_MODE) {
                return originalFetch.apply(this, arguments);
            }

            // For production, reject unauthenticated calls
            if (!DEBUG_MODE) {
                return Promise.reject(new Error('Authentication required'));
            }
        }

        // Add token to headers if not already present
        if (!options.headers || !options.headers.Authorization) {
            options.headers = options.headers || {};
            options.headers.Authorization = `Bearer ${token}`;
        }
    }

    return originalFetch.apply(this, arguments);
}; 