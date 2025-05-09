/**
 * Wizzy Account Management Module
 * Handles user account actions like password change, account deletion and session management
 */

const WizzyAccount = {
    // Configuration
    config: {
        apiEndpoints: {
            userProfile: '/api/user/profile/',
            resetPassword: '/api/auth/password/change/',
            deleteAccount: '/api/auth/account/delete/',
            logout: '/auth/logout/',
            sessions: '/api/auth/sessions/'
        },
        elements: {
            userEmail: '#userEmail',
            registrationDate: '#registrationDate',
            userRole: '#userRole',
            passwordResetForm: '#passwordResetForm',
            currentPassword: '#currentPassword',
            newPassword: '#newPassword',
            confirmPassword: '#confirmPassword',
            changePasswordBtn: '#changePasswordBtn',
            deleteAccountBtn: '#deleteAccountBtn',
            confirmDeleteAccountBtn: '#confirmDeleteAccountBtn',
            deleteAccountPassword: '#deleteAccountPassword',
            confirmDeleteCheck: '#confirmDeleteCheck',
            logoutCurrentBtn: '#logoutCurrentBtn',
            logoutAllBtn: '#logoutAllBtn'
        }
    },

    // State
    state: {
        userProfile: null,
        isLoading: false
    },

    /**
     * Initialize the account module
     */
    init: function () {
        console.log('Initializing account management module');

        // Check if user is authenticated
        if (!this.isAuthenticated()) {
            console.warn('User not authenticated, redirecting to login');
            window.location.href = '/auth/login/?next=/dashboard/#account';
            return;
        }

        // Setup event listeners
        this.setupEventListeners();

        // Load user profile data
        this.loadUserProfile();
    },

    /**
     * Check if user is authenticated
     */
    isAuthenticated: function () {
        return typeof AuthManager !== 'undefined' ?
            AuthManager.isAuthenticated() :
            !!localStorage.getItem('access_token');
    },

    /**
     * Load user profile data
     */
    loadUserProfile: function () {
        this.state.isLoading = true;
        this.showLoading(true);

        console.log('Loading user profile data...');

        const self = this;

        // Determine which API client to use
        let fetchPromise;

        if (typeof AuthManager !== 'undefined' && typeof AuthManager.fetchWithAuth === 'function') {
            console.log('Using AuthManager.fetchWithAuth to load profile');
            fetchPromise = AuthManager.fetchWithAuth(this.config.apiEndpoints.userProfile);
        } else if (typeof WizzyUtils !== 'undefined' && typeof WizzyUtils.apiRequest === 'function') {
            console.log('Using WizzyUtils.apiRequest to load profile');
            fetchPromise = WizzyUtils.apiRequest(this.config.apiEndpoints.userProfile);
        } else {
            console.log('Using direct fetch to load profile');
            // Manual fallback if neither is available
            const token = localStorage.getItem('access_token');
            const csrfToken = this.getCsrfToken();

            fetchPromise = fetch(this.config.apiEndpoints.userProfile, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                },
                credentials: 'same-origin'
            });
        }

        fetchPromise
            .then(function (response) {
                if (response.status === 401) {
                    console.warn('Authentication required for profile access');
                    self.showAlert('Vous devez être connecté pour accéder à votre profil.', 'warning');
                    return null;
                }

                if (!response.ok) {
                    throw new Error('Erreur lors du chargement du profil');
                }

                return response.json();
            })
            .then(function (data) {
                if (!data) return;

                console.log('User profile loaded successfully:', data);

                // Save profile data to state
                self.state.userProfile = data;

                // Populate the account information fields
                self.populateAccountInfo(data);
            })
            .catch(function (error) {
                console.error('Error loading user profile:', error);
                self.showAlert('Erreur lors du chargement du profil utilisateur.', 'danger');
            })
            .finally(function () {
                self.state.isLoading = false;
                self.showLoading(false);
            });
    },

    /**
     * Populate account information fields
     */
    populateAccountInfo: function (profileData) {
        if (!profileData) return;

        console.log('Populating account information fields with:', profileData);

        // Set email
        const emailElement = document.querySelector(this.config.elements.userEmail);
        if (emailElement && profileData.email) {
            emailElement.value = profileData.email;
        }

        // Set registration date
        const dateElement = document.querySelector(this.config.elements.registrationDate);
        if (dateElement && profileData.date_joined) {
            // Format date: YYYY-MM-DD to DD/MM/YYYY
            const date = new Date(profileData.date_joined);
            const formattedDate = `${date.getDate().toString().padStart(2, '0')}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getFullYear()}`;
            dateElement.value = formattedDate;
        }

        // Set user role
        const roleElement = document.querySelector(this.config.elements.userRole);
        if (roleElement && profileData.role) {
            roleElement.value = profileData.role.toUpperCase();
        }
    },

    /**
     * Set up event listeners for account actions
     */
    setupEventListeners: function () {
        // Password change form
        const passwordForm = document.querySelector(this.config.elements.passwordResetForm);
        if (passwordForm) {
            passwordForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.changePassword();
            });
        }

        // Password confirmation check
        const newPasswordInput = document.querySelector(this.config.elements.newPassword);
        const confirmPasswordInput = document.querySelector(this.config.elements.confirmPassword);

        if (newPasswordInput && confirmPasswordInput) {
            confirmPasswordInput.addEventListener('input', () => {
                if (newPasswordInput.value !== confirmPasswordInput.value) {
                    confirmPasswordInput.setCustomValidity('Les mots de passe ne correspondent pas');
                } else {
                    confirmPasswordInput.setCustomValidity('');
                }
            });
        }

        // Account deletion confirmation
        const confirmDeleteCheck = document.querySelector(this.config.elements.confirmDeleteCheck);
        const confirmDeleteButton = document.querySelector(this.config.elements.confirmDeleteAccountBtn);

        if (confirmDeleteCheck && confirmDeleteButton) {
            confirmDeleteCheck.addEventListener('change', () => {
                confirmDeleteButton.disabled = !confirmDeleteCheck.checked;
            });
        }

        // Delete account button
        const deleteAccountButton = document.querySelector(this.config.elements.confirmDeleteAccountBtn);
        if (deleteAccountButton) {
            deleteAccountButton.addEventListener('click', () => {
                this.deleteAccount();
            });
        }

        // Logout current session
        const logoutButton = document.querySelector(this.config.elements.logoutCurrentBtn);
        if (logoutButton) {
            logoutButton.addEventListener('click', () => {
                this.logoutCurrentSession();
            });
        }

        // Logout all sessions
        const logoutAllButton = document.querySelector(this.config.elements.logoutAllBtn);
        if (logoutAllButton) {
            logoutAllButton.addEventListener('click', () => {
                this.logoutAllSessions();
            });
        }
    },

    /**
     * Change user password
     */
    changePassword: function () {
        try {
            const currentPassword = document.querySelector(this.config.elements.currentPassword).value;
            const newPassword = document.querySelector(this.config.elements.newPassword).value;
            const confirmPassword = document.querySelector(this.config.elements.confirmPassword).value;

            // Validate passwords
            if (newPassword !== confirmPassword) {
                this.showAlert('Les mots de passe ne correspondent pas', 'danger');
                return;
            }

            if (newPassword.length < 8) {
                this.showAlert('Le nouveau mot de passe doit contenir au moins 8 caractères', 'danger');
                return;
            }

            // Show loading state
            const changeBtn = document.querySelector(this.config.elements.changePasswordBtn);
            if (changeBtn) {
                changeBtn.disabled = true;
                changeBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Modification en cours...';
            }

            // Use AuthManager if available, or fallback to direct fetch
            const csrfToken = typeof AuthManager !== 'undefined' ?
                AuthManager.getCsrfToken() :
                this.getCsrfToken();

            const requestOptions = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword,
                    re_new_password: confirmPassword
                })
            };

            // Add authorization if needed
            const token = localStorage.getItem('access_token');
            if (token) {
                requestOptions.headers['Authorization'] = `Bearer ${token}`;
            }

            const self = this;
            let fetchPromise;

            if (typeof AuthManager !== 'undefined') {
                fetchPromise = AuthManager.fetchWithAuth(this.config.apiEndpoints.resetPassword, requestOptions);
            } else {
                fetchPromise = fetch(this.config.apiEndpoints.resetPassword, {
                    ...requestOptions,
                    credentials: 'same-origin'
                });
            }

            fetchPromise.then(function (response) {
                // Reset button state
                if (changeBtn) {
                    changeBtn.disabled = false;
                    changeBtn.innerHTML = '<i class="fas fa-key me-2"></i> Changer le mot de passe';
                }

                if (response.ok) {
                    self.showAlert('Mot de passe modifié avec succès', 'success');
                    document.querySelector(self.config.elements.passwordResetForm).reset();
                } else {
                    return response.json().then(function (errorData) {
                        const errorMessage = errorData.detail || errorData.non_field_errors || 'Une erreur est survenue lors du changement de mot de passe';
                        self.showAlert(errorMessage, 'danger');
                    });
                }
            }).catch(function (error) {
                console.error('Error changing password:', error);
                self.showAlert('Une erreur est survenue lors du changement de mot de passe', 'danger');

                // Reset button state
                if (changeBtn) {
                    changeBtn.disabled = false;
                    changeBtn.innerHTML = '<i class="fas fa-key me-2"></i> Changer le mot de passe';
                }
            });
        } catch (error) {
            console.error('Error changing password:', error);
            this.showAlert('Une erreur est survenue lors du changement de mot de passe', 'danger');

            // Reset button state
            const changeBtn = document.querySelector(this.config.elements.changePasswordBtn);
            if (changeBtn) {
                changeBtn.disabled = false;
                changeBtn.innerHTML = '<i class="fas fa-key me-2"></i> Changer le mot de passe';
            }
        }
    },

    /**
     * Delete user account
     */
    deleteAccount: function () {
        try {
            const password = document.querySelector(this.config.elements.deleteAccountPassword).value;
            const isConfirmed = document.querySelector(this.config.elements.confirmDeleteCheck).checked;

            if (!password || !isConfirmed) {
                this.showAlert('Veuillez confirmer votre action et saisir votre mot de passe', 'danger');
                return;
            }

            // Show loading state
            const deleteBtn = document.querySelector(this.config.elements.confirmDeleteAccountBtn);
            if (deleteBtn) {
                deleteBtn.disabled = true;
                deleteBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Suppression en cours...';
            }

            // Use AuthManager if available, or fallback to direct fetch
            const csrfToken = typeof AuthManager !== 'undefined' ?
                AuthManager.getCsrfToken() :
                this.getCsrfToken();

            const requestOptions = {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    current_password: password
                })
            };

            // Add authorization if needed
            const token = localStorage.getItem('access_token');
            if (token) {
                requestOptions.headers['Authorization'] = `Bearer ${token}`;
            }

            const self = this;
            let fetchPromise;

            if (typeof AuthManager !== 'undefined') {
                fetchPromise = AuthManager.fetchWithAuth(this.config.apiEndpoints.deleteAccount, requestOptions);
            } else {
                fetchPromise = fetch(this.config.apiEndpoints.deleteAccount, {
                    ...requestOptions,
                    credentials: 'same-origin'
                });
            }

            fetchPromise.then(function (response) {
                if (response.ok || response.status === 204) {
                    // Successfully deleted account
                    self.showAlert('Votre compte a été supprimé avec succès', 'success');

                    // Clear tokens
                    localStorage.removeItem('access_token');
                    localStorage.removeItem('refresh_token');

                    // Redirect to homepage after a brief delay
                    setTimeout(function () {
                        window.location.href = '/';
                    }, 2000);
                } else {
                    return response.json().then(function (errorData) {
                        const errorMessage = errorData.detail || errorData.non_field_errors || 'Une erreur est survenue lors de la suppression du compte';
                        self.showAlert(errorMessage, 'danger');

                        // Reset button
                        if (deleteBtn) {
                            deleteBtn.disabled = false;
                            deleteBtn.innerHTML = '<i class="fas fa-trash-alt me-2"></i> Supprimer définitivement';
                        }

                        // Close modal
                        const modal = bootstrap.Modal.getInstance(document.getElementById('deleteAccountModal'));
                        if (modal) {
                            modal.hide();
                        }
                    });
                }
            }).catch(function (error) {
                console.error('Error deleting account:', error);
                self.showAlert('Une erreur est survenue lors de la suppression du compte', 'danger');

                // Reset button
                if (deleteBtn) {
                    deleteBtn.disabled = false;
                    deleteBtn.innerHTML = '<i class="fas fa-trash-alt me-2"></i> Supprimer définitivement';
                }

                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('deleteAccountModal'));
                if (modal) {
                    modal.hide();
                }
            });
        } catch (error) {
            console.error('Error deleting account:', error);
            this.showAlert('Une erreur est survenue lors de la suppression du compte', 'danger');

            // Reset button
            const deleteBtn = document.querySelector(this.config.elements.confirmDeleteAccountBtn);
            if (deleteBtn) {
                deleteBtn.disabled = false;
                deleteBtn.innerHTML = '<i class="fas fa-trash-alt me-2"></i> Supprimer définitivement';
            }

            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('deleteAccountModal'));
            if (modal) {
                modal.hide();
            }
        }
    },

    /**
     * Logout current session
     */
    logoutCurrentSession: function () {
        // Show loading
        const logoutBtn = document.querySelector(this.config.elements.logoutCurrentBtn);
        if (logoutBtn) {
            logoutBtn.disabled = true;
            logoutBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Déconnexion en cours...';
        }

        // Use AuthManager if available, or fallback to direct fetch
        const csrfToken = typeof AuthManager !== 'undefined' ?
            AuthManager.getCsrfToken() :
            this.getCsrfToken();

        const requestOptions = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                action: 'logout_current'
            })
        };

        // Add authorization if needed
        const token = localStorage.getItem('access_token');
        if (token) {
            requestOptions.headers['Authorization'] = `Bearer ${token}`;
        }

        const self = this;
        let fetchPromise;

        if (typeof AuthManager !== 'undefined') {
            fetchPromise = AuthManager.fetchWithAuth(this.config.apiEndpoints.sessions, requestOptions);
        } else {
            fetchPromise = fetch(this.config.apiEndpoints.sessions, {
                ...requestOptions,
                credentials: 'same-origin'
            });
        }

        fetchPromise.then(function (response) {
            if (response.ok) {
                // Clear tokens
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');

                // Show success message and redirect
                self.showAlert('Vous avez été déconnecté avec succès', 'success');
                setTimeout(function () {
                    window.location.href = '/auth/login/';
                }, 2000);
            } else {
                // Reset button
                if (logoutBtn) {
                    logoutBtn.disabled = false;
                    logoutBtn.innerHTML = '<i class="fas fa-sign-out-alt me-2"></i> Se déconnecter';
                }

                self.showAlert('Une erreur est survenue lors de la déconnexion', 'danger');
            }
        }).catch(function (error) {
            console.error('Error logging out current session:', error);

            // Reset button
            if (logoutBtn) {
                logoutBtn.disabled = false;
                logoutBtn.innerHTML = '<i class="fas fa-sign-out-alt me-2"></i> Se déconnecter';
            }

            self.showAlert('Une erreur est survenue lors de la déconnexion', 'danger');
        });
    },

    /**
     * Logout all active sessions
     */
    logoutAllSessions: function () {
        // Show loading
        const logoutAllBtn = document.querySelector(this.config.elements.logoutAllBtn);
        if (logoutAllBtn) {
            logoutAllBtn.disabled = true;
            logoutAllBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Déconnexion en cours...';
        }

        // Use AuthManager if available, or fallback to direct fetch
        const csrfToken = typeof AuthManager !== 'undefined' ?
            AuthManager.getCsrfToken() :
            this.getCsrfToken();

        const requestOptions = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                action: 'logout_all'
            })
        };

        // Add authorization if needed
        const token = localStorage.getItem('access_token');
        if (token) {
            requestOptions.headers['Authorization'] = `Bearer ${token}`;
        }

        const self = this;
        let fetchPromise;

        if (typeof AuthManager !== 'undefined') {
            fetchPromise = AuthManager.fetchWithAuth(this.config.apiEndpoints.sessions, requestOptions);
        } else {
            fetchPromise = fetch(this.config.apiEndpoints.sessions, {
                ...requestOptions,
                credentials: 'same-origin'
            });
        }

        fetchPromise.then(function (response) {
            if (response.ok) {
                // Clear tokens
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');

                // Show success message and redirect
                self.showAlert('Toutes vos sessions ont été déconnectées', 'success');
                setTimeout(function () {
                    window.location.href = '/auth/login/';
                }, 2000);
            } else {
                // Reset button
                if (logoutAllBtn) {
                    logoutAllBtn.disabled = false;
                    logoutAllBtn.innerHTML = '<i class="fas fa-sign-out-alt me-2"></i> Déconnecter toutes les sessions';
                }

                self.showAlert('Une erreur est survenue lors de la déconnexion des sessions', 'danger');
            }
        }).catch(function (error) {
            console.error('Error logging out all sessions:', error);

            // Reset button
            if (logoutAllBtn) {
                logoutAllBtn.disabled = false;
                logoutAllBtn.innerHTML = '<i class="fas fa-sign-out-alt me-2"></i> Déconnecter toutes les sessions';
            }

            self.showAlert('Une erreur est survenue lors de la déconnexion des sessions', 'danger');
        });
    },

    /**
     * Get CSRF token from cookies
     */
    getCsrfToken: function () {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; csrftoken=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    },

    /**
     * Show loading indicator
     */
    showLoading: function (show = true) {
        // Add loading class to body
        if (show) {
            document.body.classList.add('is-loading');
        } else {
            document.body.classList.remove('is-loading');
        }

        // Handle loading spinners in the account tab
        const spinners = document.querySelectorAll('.loading-spinner');
        spinners.forEach(spinner => {
            if (show) {
                spinner.classList.remove('d-none');
            } else {
                spinner.classList.add('d-none');
            }
        });
    },

    /**
     * Show alert message
     */
    showAlert: function (message, type = 'info') {
        if (typeof WizzyUtils !== 'undefined' && WizzyUtils.showAlert) {
            WizzyUtils.showAlert(message, type);
            return;
        }

        // Fallback alert implementation
        const alertsContainer = document.getElementById('alertsContainer');
        if (!alertsContainer) return;

        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.setAttribute('role', 'alert');
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

        alertsContainer.appendChild(alertDiv);

        // Auto-dismiss after 5 seconds
        setTimeout(function () {
            alertDiv.classList.remove('show');
            setTimeout(function () {
                alertDiv.remove();
            }, 150);
        }, 5000);
    }
};

// No need for DOM ready handler, WizzyDashboard will call init() when tab is activated 