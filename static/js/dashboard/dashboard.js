/**
 * Wizzy Dashboard Main Module
 * Initializes and coordinates all dashboard components
 */

const WizzyDashboard = {
    // Track active tab
    activeTab: 'overview',

    // Initialize the dashboard
    init: function () {
        console.log('Initializing Wizzy Dashboard');

        // Check if user is authenticated
        if (!WizzyUtils.isAuthenticated()) {
            return;
        }

        // Show a welcome message with the appropriate plan level
        this.showWelcomeMessage();

        // Initialize tabs
        this.loadInitialTab();
        this.setupTabNavigation();
    },

    // Setup tab navigation
    setupTabNavigation: function () {
        const tabLinks = document.querySelectorAll('.nav-link[data-tab]');

        tabLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const tabId = link.getAttribute('data-tab');
                this.switchTab(tabId);
            });
        });

        // Check if URL has hash for direct tab access
        if (window.location.hash) {
            const tabId = window.location.hash.substring(1);
            this.switchTab(tabId);
        }
    },

    // Load the initial dashboard tab
    loadInitialTab: function () {
        // Get active tab from URL hash or default to overview
        const tabId = window.location.hash ? window.location.hash.substring(1) : 'overview';
        this.switchTab(tabId);
    },

    // Switch between dashboard tabs
    switchTab: function (tabId) {
        // Hide all tab content
        document.querySelectorAll('.tab-pane').forEach(tab => {
            tab.classList.remove('show', 'active');
        });

        // Deactivate all nav links
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });

        // First try with the standard format "tabId-tab"
        let selectedTab = document.getElementById(`${tabId}-tab`);

        // If not found, try with just the tabId (for account tab)
        if (!selectedTab) {
            selectedTab = document.getElementById(tabId);
        }

        const navLink = document.querySelector(`.nav-link[data-tab="${tabId}"]`);

        if (selectedTab) {
            selectedTab.classList.add('show', 'active');
        } else {
            console.error(`Tab content not found for tab ID: ${tabId}`);
        }

        if (navLink) {
            navLink.classList.add('active');
        } else {
            console.error(`Nav link not found for tab ID: ${tabId}`);
        }

        // Update active tab
        this.activeTab = tabId;

        // Update URL hash without scrolling
        const scrollPosition = window.pageYOffset;
        window.location.hash = tabId;
        window.scrollTo(0, scrollPosition);

        // Initialize content for the selected tab
        this.loadTabContent(tabId);
    },

    // Load content for selected tab
    loadTabContent: function (tabId) {
        // Initialize the appropriate module based on the tab
        try {
            switch (tabId) {
                case 'overview':
                    if (typeof WizzyDashboardOverview !== 'undefined') {
                        WizzyDashboardOverview.init();
                    } else {
                        console.error('Dashboard overview module not found');
                    }
                    break;

                case 'structures':
                    if (typeof WizzyScrapingStructures !== 'undefined') {
                        WizzyScrapingStructures.init();
                    } else {
                        console.error('Scraping structures module not found');
                    }
                    break;

                case 'scraping':
                    if (typeof WizzyScrapingJobs !== 'undefined') {
                        WizzyScrapingJobs.init();
                    } else {
                        console.error('Scraping jobs module not found');
                        // Display a message instead of just failing
                        const container = document.getElementById('activeScrapingTasks');
                        if (container) {
                            container.innerHTML = `
                                <div class="alert alert-info">
                                    <p>Le module de gestion des tâches est en cours de chargement...</p>
                                </div>
                            `;
                        }
                    }
                    break;

                case 'leads':
                    if (typeof WizzyIndustryEnrichment !== 'undefined') {
                        WizzyIndustryEnrichment.init();
                    } else {
                        console.error('Industry enrichment module not found');
                        // Display a message instead of just failing
                        const recommendationsContainer = document.getElementById('recommendationsContainer');
                        if (recommendationsContainer) {
                            recommendationsContainer.innerHTML = `
                                <div class="alert alert-info">
                                    <p>Le module d'enrichissement d'industrie est en cours de chargement...</p>
                                </div>
                            `;
                        }
                    }
                    break;

                case 'billing':
                    if (typeof WizzyBilling !== 'undefined') {
                        WizzyBilling.init();
                    } else {
                        console.error('Billing module not found');
                    }
                    break;

                case 'account':
                    if (typeof WizzyAccount !== 'undefined') {
                        WizzyAccount.init();
                    } else {
                        console.error('Account management module not found');
                        // Display a message if module isn't loaded
                        const accountContainer = document.getElementById('account-tab');
                        if (accountContainer) {
                            accountContainer.innerHTML += `
                                <div class="alert alert-info">
                                    <p>Le module de gestion de compte est en cours de chargement...</p>
                                </div>
                            `;
                        } else {
                            console.error('Could not find account tab container with ID "account-tab"');
                        }
                    }
                    break;

                default:
                    console.error('Unknown tab:', tabId);
                    break;
            }
        } catch (error) {
            console.error(`Error initializing ${tabId} module:`, error);
            // Add graceful recovery - display an error message in the tab
            let tabPane = document.getElementById(`${tabId}-tab`);
            if (!tabPane) {
                // Try without the "-tab" suffix
                tabPane = document.getElementById(tabId);
            }

            if (tabPane) {
                tabPane.innerHTML += `
                    <div class="alert alert-danger">
                        <p>Une erreur est survenue lors du chargement de ce module. Veuillez rafraîchir la page ou contacter le support.</p>
                    </div>
                `;
            }
        }
    },

    // Show welcome message based on user's plan
    showWelcomeMessage: function () {
        // Get user plan data
        let userPlan = 'free'; // Default to free
        const userRoleElement = document.querySelector('[data-user-role]');
        if (userRoleElement) {
            userPlan = userRoleElement.dataset.userRole;
        }

        // Create a personalized message based on plan level
        let welcomeMessage = '';
        let messageClass = '';

        switch (userPlan) {
            case 'premium':
                welcomeMessage = 'Bienvenue sur votre dashboard <strong>Wizzy Premium</strong>. Vous bénéficiez de tous les avantages premium, y compris l\'équipe Closer pour finaliser vos ventes.';
                messageClass = 'alert-primary';
                break;
            case 'classic':
                welcomeMessage = 'Bienvenue sur votre dashboard <strong>Wizzy Classique</strong>. Profitez du scraping avancé et de l\'automatisation des messages personnalisés.';
                messageClass = 'alert-info';
                break;
            default:
                welcomeMessage = 'Bienvenue sur votre dashboard <strong>Wizzy Free</strong>. Découvrez les fonctionnalités de base et envisagez une mise à niveau pour débloquer tout le potentiel de Wizzy.';
                messageClass = 'alert-secondary';
        }

        // Show the message briefly
        const alertsContainer = document.getElementById('alertsContainer');
        if (alertsContainer) {
            const alert = document.createElement('div');
            alert.className = `alert ${messageClass} alert-dismissible fade show`;
            alert.innerHTML = `
                ${welcomeMessage}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            `;
            alertsContainer.appendChild(alert);

            // Auto-dismiss after 7 seconds
            setTimeout(() => {
                try {
                    const bsAlert = bootstrap.Alert.getInstance(alert);
                    if (bsAlert) {
                        bsAlert.close();
                    } else {
                        alert.remove();
                    }
                } catch (e) {
                    alert.remove();
                }
            }, 7000);
        }
    },

    // Get user profile data
    fetchUserProfile: async function () {
        try {
            const response = await WizzyUtils.apiRequest('/api/user/profile/');

            if (response.ok) {
                return await response.json();
            } else if (response.status === 401) {
                this.showAuthRequired();
                return null;
            } else {
                WizzyUtils.showAlert('Erreur lors du chargement du profil', 'danger');
                return null;
            }
        } catch (error) {
            console.error('Error fetching user profile:', error);
            WizzyUtils.showAlert('Erreur lors du chargement du profil', 'danger');
            return null;
        }
    }
};

// Initialize the dashboard when the DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    WizzyDashboard.init();
});