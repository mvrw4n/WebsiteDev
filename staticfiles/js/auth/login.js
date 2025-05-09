/**
 * Login form handler
 */

document.addEventListener('DOMContentLoaded', function () {
    const loginForm = document.getElementById('login-form');

    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            // Get form data
            const formData = new FormData(loginForm);
            const email = formData.get('email');
            const password = formData.get('password');

            // Display loading state
            const submitBtn = loginForm.querySelector('button[type="submit"]');
            const originalBtnText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Connexion en cours...';

            // Clear previous error messages
            document.getElementById('login-error')?.remove();

            try {
                // Make login request
                const response = await fetch('/auth/jwt/create/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': AuthManager.getCsrfToken()
                    },
                    body: JSON.stringify({ email, password })
                });

                const data = await response.json();

                if (!response.ok) {
                    // Show error message
                    const errorMsg = data.detail || 'Identifiants incorrects. Veuillez réessayer.';
                    showError(errorMsg);
                    return;
                }

                // Save tokens using AuthManager
                if (AuthManager.handleLoginResponse(data)) {
                    // Redirect to dashboard
                    window.location.href = '/dashboard/';
                } else {
                    showError('Erreur lors de la connexion. Tokens invalides.');
                }

            } catch (error) {
                console.error('Login error:', error);
                showError('Une erreur est survenue lors de la connexion.');
            } finally {
                // Restore button state
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnText;
            }
        });
    }

    function showError(message) {
        // Remove existing error message if any
        document.getElementById('login-error')?.remove();

        // Create error element
        const errorElement = document.createElement('div');
        errorElement.id = 'login-error';
        errorElement.className = 'alert alert-danger mt-3';
        errorElement.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;

        // Insert after form
        loginForm.insertAdjacentElement('afterend', errorElement);
    }
}); 