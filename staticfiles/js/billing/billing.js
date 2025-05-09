/**
 * Wizzy Billing Module
 * Handles subscription management and payment processing
 */

const WizzyBilling = {
    // Configuration
    config: {
        stripePublicKey: 'pk_test_51R6fGIFbWog8HEBlvohdOkLhihoiNtmJyvHtbg8WnMq2eHxLubNUij4gZx2vQsKeP4w1Gxz8PEFrBWNAbX66DJbB00c3OsK3XU',
        apiEndpoints: {
            subscription: '/api/billing/subscription/',
            updatePlan: '/api/billing/plan/update/',
            additionalLeads: '/api/billing/leads/purchase/'
        }
    },

    // State
    state: {
        currentSubscription: null,
        availablePlans: [],
        stripeElements: null,
        cardElement: null,
        paymentFormVisible: false,
        selectedPlan: null,
        isPremiumUser: false,
        userProfile: {},
        leadPacks: [],
        canPurchaseLeads: false
    },

    /**
     * Initialize the billing module
     */
    init: function () {
        console.log('Initializing billing module');

        // Check authentication
        if (!WizzyUtils.isAuthenticated()) {
            return;
        }

        // Get Stripe key if available
        const stripeKeyElement = document.getElementById('stripe-key');
        if (stripeKeyElement) {
            this.config.stripePublicKey = stripeKeyElement.value;
        }

        // Initialize Stripe if available
        if (this.config.stripePublicKey && typeof Stripe !== 'undefined') {
            this.initializeStripe();
        }

        // Determine if user has premium account
        this.checkPremiumStatus();

        // Load subscription data
        this.loadSubscriptionData();

        // Set up event listeners
        this.setupEventListeners();

        // Make sure sections are in the correct order
        this.reorderSections();

        // Clean up on page unload
        window.addEventListener('beforeunload', () => {
            if (this.refreshTimeout) {
                clearTimeout(this.refreshTimeout);
            }
        });
    },

    /**
     * Check if user has a premium account
     */
    checkPremiumStatus: function () {
        // Check if user-role data attribute is available
        const userRoleElement = document.querySelector('[data-user-role]');
        if (userRoleElement) {
            const userRole = userRoleElement.dataset.userRole.toLowerCase();
            this.state.isPremiumUser = ['classic', 'premium', 'lifetime'].includes(userRole);
            console.log('User premium status:', this.state.isPremiumUser, '(Role:', userRole, ')');
        } else {
            // Default to false if we can't determine
            this.state.isPremiumUser = false;
            console.log('Could not determine user premium status, defaulting to false');
        }
    },

    /**
     * Initialize Stripe elements
     */
    initializeStripe: function () {
        // Initialize Stripe with the public key
        const stripe = Stripe(this.config.stripePublicKey);

        // Create Stripe elements
        const elements = stripe.elements();

        // Create card element
        const cardElement = elements.create('card', {
            style: {
                base: {
                    fontSize: '16px',
                    color: '#32325d',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
                    '::placeholder': {
                        color: '#aab7c4'
                    }
                },
                invalid: {
                    color: '#dc3545',
                    iconColor: '#dc3545'
                }
            }
        });

        // Store elements in state
        this.state.stripeElements = elements;
        this.state.cardElement = cardElement;

        // Render card element
        const cardElementMount = document.getElementById('card-element');
        if (cardElementMount) {
            cardElement.mount('#card-element');

            // Add event listeners for validation
            cardElement.addEventListener('change', (event) => {
                const displayError = document.getElementById('card-errors');
                if (event.error) {
                    displayError.textContent = event.error.message;
                } else {
                    displayError.textContent = '';
                }
            });
        }
    },

    /**
     * Load subscription data and user profile information
     */
    loadSubscriptionData: async function () {
        try {
            // Add cache busting to prevent stale data
            const timestamp = new Date().getTime();
            console.log('Loading subscription data...');

            // First try to load from API
            let success = false;
            let data = {};

            try {
                const response = await fetch(`/api/dashboard/subscription/?_=${timestamp}`);

                if (response.ok) {
                    data = await response.json();
                    success = true;
                } else {
                    console.warn('Subscription API returned status:', response.status);
                }
            } catch (apiError) {
                console.warn('Error fetching subscription data from API:', apiError);
            }

            // If API succeeded, use that data
            if (success) {
                console.log('Successfully loaded subscription data from API');
                this.state.currentSubscription = data.subscription || null;
                this.state.availablePlans = data.available_plans || [];
                this.state.userProfile = data.profile || {};
                this.state.leadPacks = data.lead_packs || [];

                // Set role-based state
                const role = this.state.userProfile.role || 'free';
                this.state.isPremiumUser = ['classic', 'premium', 'lifetime'].includes(role);
                this.state.canPurchaseLeads = this.state.userProfile.can_purchase_additional_leads || false;

                // Render the subscription UI
                this.renderCurrentSubscription(data);
                this.renderAvailablePlans(data.available_plans);
                this.renderAdditionalLeads(data);
            } else {
                // If API failed, use placeholder data
                console.log('Using placeholder subscription data');
                this.renderPlaceholderSubscription();
            }

            // Set a timeout to refresh data every 60 seconds
            if (this.refreshTimeout) {
                clearTimeout(this.refreshTimeout);
            }
            this.refreshTimeout = setTimeout(() => {
                this.loadSubscriptionData();
            }, 60000);

        } catch (error) {
            console.error('Error in subscription data loading process:', error);
            // Show placeholder UI as a fallback
            this.renderPlaceholderSubscription();
        }
    },

    /**
     * Load placeholder subscription data
     * This is only for development while API endpoints are not available
     */
    loadPlaceholderData: function () {
        // Get user plan data
        let userPlan = 'free'; // Default to free
        const userRoleElement = document.querySelector('[data-user-role]');
        if (userRoleElement) {
            userPlan = userRoleElement.dataset.userRole;
        }

        // Update premium status based on plan
        this.state.isPremiumUser = userPlan !== 'free';

        // Subscription plans based on the provided information
        const placeholderPlans = [
            {
                id: 1,
                name: 'Wizzy Free',
                price: 0,
                interval: 'mois',
                leads_quota: 5,
                unlimited_leads: false,
                features: [
                    'Scraping de haute qualité limité',
                    'Maximum d\'informations',
                    'Prompts personnalisés pour approcher les clients',
                    'Conseils personnalisés spécifiques à votre service/bien',
                    'IA qui parle'
                ]
            },
            {
                id: 2,
                name: 'Wizzy Classique',
                price: 80,
                interval: 'mois',
                leads_quota: 100,
                unlimited_leads: false,
                features: [
                    'Scraping illimité (100/jour)',
                    'Maximum d\'informations',
                    'Automatisation des messages personnalisés',
                    'Scraping de haute qualité sur tous les sites y compris les réseaux sociaux',
                    'Prompts personnalisés pour approcher les clients',
                    'Conseils personnalisés spécifiques à votre service/bien',
                    'Possibilité de discuter avec l\'IA librement, IA qui parle'
                ]
            }
        ];

        // Select the appropriate plan and usage data
        let userPlanIndex = 0;
        let leadsUsed = 0;

        switch (userPlan) {
            case 'classic':
                userPlanIndex = 1;
                leadsUsed = Math.floor(Math.random() * 70) + 30; // Between 30-100
                break;
            case 'premium_closing':
                userPlanIndex = 2;
                leadsUsed = Math.floor(Math.random() * 100) + 50; // Between 50-150
                break;
            case 'premium_scaling':
                userPlanIndex = 3;
                leadsUsed = Math.floor(Math.random() * 100) + 50; // Between 50-150
                break;
            default: // free
                userPlanIndex = 0;
                leadsUsed = Math.floor(Math.random() * 5);
        }

        // Create placeholder subscription
        const placeholderSubscription = {
            id: 1,
            status: 'active',
            plan: placeholderPlans[userPlanIndex],
            current_usage: {
                leads_used: leadsUsed,
                structures_count: userPlanIndex === 0 ? 1 : (userPlanIndex === 1 ? 5 : 12),
                active_structures: userPlanIndex === 0 ? 1 : (userPlanIndex === 1 ? 3 : 8)
            },
            start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(), // 30 days ago
            next_billing_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString() // 30 days from now
        };

        // Store data
        this.state.currentSubscription = placeholderSubscription;
        this.state.availablePlans = placeholderPlans;

        // Render UI
        this.renderCurrentSubscription(placeholderSubscription);
        // Render additional leads section immediately after current subscription
        this.renderAdditionalLeadsSection(placeholderSubscription);
        // Render subscription plans last
        this.renderSubscriptionPlans(placeholderPlans);
    },

    /**
     * Show loading state for a section
     * @param {string} sectionId - ID of the section
     */
    showLoadingState: function (sectionId) {
        const section = document.getElementById(sectionId);
        if (section) {
            section.innerHTML = `
                <div class="text-center py-3">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Chargement...</span>
                    </div>
                    <p class="mt-2">Chargement des données...</p>
                </div>
            `;
        }
    },

    /**
     * Render current subscription information
     * @param {object} subscription - Subscription data
     */
    renderCurrentSubscription: function (subscription) {
        const container = document.getElementById('currentSubscription');
        if (!container) return;

        if (!subscription) {
            container.innerHTML = `
                <div class="alert alert-info">
                    <h5 class="alert-heading">Aucun abonnement actif</h5>
                    <p>Vous n'avez pas encore d'abonnement actif. Veuillez choisir un plan ci-dessous.</p>
                </div>
            `;
            return;
        }

        const plan = subscription.plan || {};
        const usage = subscription.current_usage || {};

        const leadsUsed = usage.leads_used || 0;
        const leadsQuota = plan.leads_quota || 0;
        const unlimited = plan.unlimited_leads || false;

        const usagePercent = unlimited ? 0 : Math.min(Math.round((leadsUsed / leadsQuota) * 100), 100);
        const nextBillingDate = subscription.next_billing_date
            ? WizzyUtils.formatDate(subscription.next_billing_date, false)
            : 'N/A';

        container.innerHTML = `
            <div class="card mb-4">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h5 class="card-title mb-0">Votre abonnement actuel</h5>
                    <span class="badge bg-success">Actif</span>
                </div>
                <div class="card-body">
                    <h4 class="mb-3">${plan.name || 'Plan inconnu'}</h4>
                    
                    <div class="mb-4">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span>Utilisation des leads</span>
                            <span>${unlimited ? 'Illimité' : `${leadsUsed} / ${leadsQuota}`}</span>
                        </div>
                        <div class="progress" style="height: 8px;">
                            <div class="progress-bar ${usagePercent > 80 ? 'bg-danger' : 'bg-primary'}" 
                                 role="progressbar" style="width: ${usagePercent}%" 
                                 aria-valuenow="${leadsUsed}" aria-valuemin="0" aria-valuemax="${leadsQuota}"></div>
                        </div>
                    </div>
                    
                    <ul class="list-group mb-4">
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span>Prix mensuel</span>
                            <span class="fw-bold">${WizzyUtils.formatCurrency(plan.price || 0)}</span>
                        </li>
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span>Prochain paiement</span>
                            <span>${nextBillingDate}</span>
                        </li>
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span>Structures actives</span>
                            <span>${usage.active_structures || 0}</span>
                        </li>
                    </ul>
                    
                    <button class="btn btn-outline-primary" id="changePlanBtn">
                        <i class="fas fa-exchange-alt"></i> Changer de plan
                    </button>
                </div>
            </div>
        `;

        // Add event listener for change plan button
        const changePlanBtn = document.getElementById('changePlanBtn');
        if (changePlanBtn) {
            changePlanBtn.addEventListener('click', () => {
                // Redirect to pricing page
                window.location.href = 'http://127.0.0.1:8000/pricing/';
            });
        }
    },

    /**
     * Render available subscription plans
     * @param {array} plans - Available subscription plans
     */
    renderSubscriptionPlans: function (plans) {
        const container = document.getElementById('subscriptionPlans');
        if (!container) return;

        if (!plans || !plans.length) {
            container.innerHTML = '<div class="alert alert-info">Aucun plan disponible actuellement.</div>';
            return;
        }

        // Get current plan ID
        const currentPlanId = this.state.currentSubscription?.plan?.id;

        // Create HTML
        let html = `
            <div class="card mb-4">
                <div class="card-header">
                    <h5 class="card-title mb-0">Plans d'abonnement disponibles</h5>
                </div>
                <div class="card-body">
                    <div class="row">
        `;

        // Add plan cards
        plans.forEach(plan => {
            const isCurrent = plan.id === currentPlanId;

            html += `
                <div class="col-md-4 mb-4">
                    <div class="card h-100 ${isCurrent ? 'border-primary' : ''}">
                        <div class="card-header ${isCurrent ? 'bg-primary text-white' : ''}">
                            <h5 class="card-title mb-0">${plan.name}</h5>
                            ${isCurrent ? '<span class="badge bg-light text-primary float-end">Plan actuel</span>' : ''}
                        </div>
                        <div class="card-body d-flex flex-column">
                            <div class="pricing-amount mb-3">
                                ${WizzyUtils.formatCurrency(plan.price)}
                                <span class="period">/${plan.interval}</span>
                            </div>
                            
                            <div class="mb-3">
                                ${plan.unlimited_leads
                    ? '<span class="badge bg-success">Leads illimités</span>'
                    : `<span class="badge bg-primary">${plan.leads_quota} leads inclus</span>`}
                            </div>
                            
                            <ul class="feature-list mb-4">
                                ${plan.features.map(feature => `
                                    <li><i class="fas fa-check-circle"></i> ${feature}</li>
                                `).join('')}
                            </ul>
                            
                            <button class="btn ${isCurrent ? 'btn-outline-primary disabled' : 'btn-primary'} mt-auto" 
                                    onclick="WizzyBilling.selectPlan(${plan.id})" 
                                    ${isCurrent ? 'disabled' : ''}>
                                ${isCurrent ? 'Plan actuel' : 'Sélectionner'}
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });

        html += `
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = html;
    },

    /**
     * Render additional leads section
     * @param {object} data - Subscription data
     */
    renderAdditionalLeads: function (data) {
        // For backward compatibility
        if (typeof this.renderAdditionalLeadsSection === 'function') {
            return this.renderAdditionalLeadsSection(data.subscription || data);
        }

        const container = document.getElementById('additionalLeadsSection');
        if (!container) return;

        // Check if user can purchase additional leads
        const canPurchase = data.profile?.can_purchase_additional_leads ||
            (data.userProfile?.can_purchase_additional_leads) ||
            this.state.canPurchaseLeads;

        if (!canPurchase) {
            container.innerHTML = `
                <div class="card mb-4">
                    <div class="card-header">
                        <h5 class="mb-0">Leads supplémentaires</h5>
                    </div>
                    <div class="card-body">
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle me-2"></i>
                            Cette fonctionnalité est disponible uniquement avec les abonnements Classique et Premium.
                        </div>
                        <p>Passez à un abonnement supérieur pour pouvoir acheter des leads supplémentaires.</p>
                    </div>
                </div>
            `;
            return;
        }

        // Render lead purchase form
        container.innerHTML = `
            <div class="card mb-4">
                <div class="card-header">
                    <h5 class="mb-0">Acheter des leads supplémentaires</h5>
                </div>
                <div class="card-body">
                    <p>Vous pouvez acheter des leads supplémentaires qui seront ajoutés à votre quota mensuel.</p>
                    
                    <div class="mb-3">
                        <label for="leadQuantitySlider" class="form-label">Nombre de leads</label>
                        <input type="range" class="form-range" min="20" max="1000" step="10" value="100" id="leadQuantitySlider">
                        <div class="d-flex justify-content-between">
                            <span>20</span>
                            <span class="fw-bold" id="leadQuantityDisplay">100</span>
                            <span>1000</span>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <div class="lead-pricing-container">
                            <div class="lead-pricing-box text-center p-3 border rounded">
                                <h6>Prix total</h6>
                                <div class="lead-price display-6 mb-2" id="leadPriceDisplay">20,00 €</div>
                                <div class="text-muted small">Prix unitaire: 0,20 € par lead</div>
                            </div>
                        </div>
                    </div>
                    
                    <button id="purchaseLeadsBtn" class="btn btn-primary">
                        Acheter des leads supplémentaires
                    </button>
                </div>
            </div>
        `;

        // Setup the slider
        this.setupLeadSlider();
    },

    /**
     * Purchase a pack of leads
     * @param {number} quantity - Number of leads to purchase
     * @param {number} price - Price of the lead pack
     */
    purchaseLeadPack: function (quantity, price) {
        // If not premium, show a message and return
        if (!this.state.isPremiumUser) {
            WizzyUtils.showAlert('Vous devez passer à un abonnement premium pour acheter des leads supplémentaires.', 'warning');
            return;
        }

        // If Stripe is not initialized or no active subscription, show error
        if (!this.state.stripeElements || !this.state.currentSubscription) {
            WizzyUtils.showAlert('Une erreur est survenue. Veuillez vérifier que vous avez un abonnement actif.', 'danger');
            return;
        }

        // Show payment form
        this.showPaymentForm({
            title: 'Acheter des leads supplémentaires',
            description: `Vous êtes sur le point d'acheter ${quantity} leads pour ${WizzyUtils.formatCurrency(price)}.`,
            submitButtonText: 'Payer et ajouter les leads',
            onSubmit: async (token) => {
                // Mock API call for now
                WizzyUtils.showAlert(`Achat de ${quantity} leads en cours de traitement...`, 'info');

                // In the real implementation, this would call the purchaseLeads API endpoint
                setTimeout(() => {
                    WizzyUtils.showAlert(`${quantity} leads ont été ajoutés à votre compte!`, 'success');
                    this.loadSubscriptionData(); // Refresh data
                    this.hidePaymentForm();
                }, 2000);
            }
        });
    },

    /**
     * Select a subscription plan for purchase/update
     * @param {number} planId - Plan ID
     */
    selectPlan: function (planId) {
        console.log('Plan selected:', planId);

        // Find the selected plan from available plans
        let selectedPlan = null;

        if (this.state && this.state.availablePlans) {
            selectedPlan = this.state.availablePlans.find(p => p.id === planId);
        } else if (document.querySelector(`[data-plan-id="${planId}"]`)) {
            // Try to get plan info from the DOM if state not available
            const planElement = document.querySelector(`[data-plan-id="${planId}"]`).closest('.card');
            if (planElement) {
                const nameElement = planElement.querySelector('.card-header h5');
                const priceElement = planElement.querySelector('.price-tag .display-5');

                selectedPlan = {
                    id: planId,
                    name: nameElement ? nameElement.textContent : `Plan ${planId}`,
                    price: priceElement ? parseFloat(priceElement.textContent) : 0
                };
            }
        }

        if (selectedPlan) {
            // Display a message to the user
            const message = `Vous avez sélectionné le plan ${selectedPlan.name}. ` +
                `Cette fonctionnalité n'est pas encore disponible en mode hors ligne.`;

            alert(message);

            // For a richer UI, we could show a modal or redirect to a payment page
            // when the payment system is implemented
        } else {
            alert('Impossible de trouver les détails du plan. Veuillez réessayer plus tard.');
        }
    },

    /**
     * Show payment form for selected plan
     * @param {object} plan - Selected plan
     */
    showPaymentForm: function (plan) {
        const container = document.getElementById('paymentFormContainer');
        if (!container) return;

        // Update payment button text
        const paymentButton = document.getElementById('payment-button');
        if (paymentButton) {
            const isUpdate = this.state.currentSubscription && this.state.currentSubscription.plan;
            paymentButton.textContent = isUpdate ? 'Mettre à jour l\'abonnement' : 'Payer et s\'abonner';
        }

        // Show the payment form
        container.classList.remove('d-none');
        container.scrollIntoView({ behavior: 'smooth' });

        // Set state
        this.state.paymentFormVisible = true;
    },

    /**
     * Hide payment form
     */
    hidePaymentForm: function () {
        const container = document.getElementById('paymentFormContainer');
        if (container) {
            container.classList.add('d-none');
        }

        // Reset state
        this.state.paymentFormVisible = false;
        this.state.selectedPlan = null;
    },

    /**
     * Process payment
     */
    processPayment: async function () {
        // Placeholder for payment processing
        WizzyUtils.showAlert('Fonctionnalité de paiement en cours de développement', 'info');

        // Hide payment form
        this.hidePaymentForm();
    },

    /**
     * Setup event listeners
     */
    setupEventListeners: function () {
        // Payment button
        const paymentButton = document.getElementById('payment-button');
        if (paymentButton) {
            paymentButton.addEventListener('click', this.processPayment.bind(this));
        }
    },

    /**
     * Ensure sections are in the correct order in the DOM
     */
    reorderSections: function () {
        // We need to wait for the subscription data to load
        setTimeout(() => {
            // Get references to all sections
            const subscriptionSection = document.getElementById('currentSubscription');
            const leadsSection = document.getElementById('additionalLeadsSection');
            const plansSection = document.getElementById('subscriptionPlans');

            if (subscriptionSection && leadsSection && plansSection) {
                const container = subscriptionSection.parentNode;

                // Make sure leads section comes right after subscription section
                if (subscriptionSection.nextElementSibling !== leadsSection) {
                    // Insert the leads section after subscription section
                    container.insertBefore(leadsSection, subscriptionSection.nextElementSibling);
                }

                // Make sure plans section comes after leads section
                if (leadsSection.nextElementSibling !== plansSection) {
                    // Insert the plans section after leads section
                    container.insertBefore(plansSection, leadsSection.nextElementSibling);
                }

                console.log('Sections reordered: subscription > leads > plans');
            }
        }, 100); // Small delay to ensure sections are loaded
    },

    /**
     * Render placeholder subscription when data loading fails
     */
    renderPlaceholderSubscription: function () {
        console.log('Rendering placeholder subscription');

        // Get user plan data (as with subscription data)
        let userPlan = 'free'; // Default to free
        const userRoleElement = document.querySelector('[data-user-role]');
        if (userRoleElement) {
            userPlan = userRoleElement.dataset.userRole;
        }

        // Create placeholder data
        const placeholderData = {
            subscription: {
                plan_name: userPlan === 'premium' ? 'Wizzy Premium' : (userPlan === 'classic' ? 'Wizzy Classique' : 'Wizzy Free'),
                status: 'active',
                current_period_end: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
                cancel_at_period_end: false
            },
            profile: {
                leads_used: 0,
                leads_quota: userPlan === 'premium' ? 300 : (userPlan === 'classic' ? 100 : 5),
                unlimited_leads: userPlan === 'lifetime',
                can_purchase_additional_leads: ['classic', 'premium'].includes(userPlan)
            },
            available_plans: [
                {
                    id: 1,
                    name: 'Wizzy Free',
                    price: 0,
                    interval: 'mois',
                    leads_quota: 5,
                    features: [
                        'Accès basique aux outils',
                        'Support par email',
                        '5 leads par mois'
                    ]
                },
                {
                    id: 2,
                    name: 'Wizzy Classique',
                    price: 49,
                    interval: 'mois',
                    leads_quota: 100,
                    features: [
                        'Toutes les fonctionnalités',
                        'Support prioritaire',
                        '100 leads par mois',
                        'Achat de leads supplémentaires'
                    ]
                },
                {
                    id: 3,
                    name: 'Wizzy Premium',
                    price: 99,
                    interval: 'mois',
                    leads_quota: 300,
                    features: [
                        'Toutes les fonctionnalités',
                        'Support VIP',
                        '300 leads par mois',
                        'Achat de leads supplémentaires',
                        'API Access'
                    ]
                }
            ]
        };

        // Render using the appropriate rendering methods or fallback to direct DOM manipulation

        // Check if renderCurrentSubscription exists
        if (typeof this.renderCurrentSubscription === 'function') {
            this.renderCurrentSubscription(placeholderData);
        } else {
            // Fallback rendering for current subscription
            this.renderSubscriptionDirectly(placeholderData);
        }

        // Check if renderAvailablePlans exists
        if (typeof this.renderAvailablePlans === 'function') {
            this.renderAvailablePlans(placeholderData.available_plans);
        } else {
            // Fallback rendering for available plans
            this.renderPlansDirectly(placeholderData.available_plans);
        }

        // Check if renderAdditionalLeads exists
        if (typeof this.renderAdditionalLeads === 'function') {
            this.renderAdditionalLeads(placeholderData);
        } else if (typeof this.renderAdditionalLeadsSection === 'function') {
            // Try alternative method if available
            this.renderAdditionalLeadsSection(placeholderData.subscription);
        }
    },

    /**
     * Fallback method to render current subscription directly to DOM
     * @param {Object} data - Subscription data object
     */
    renderSubscriptionDirectly: function (data) {
        const subscriptionContainer = document.getElementById('currentSubscription');
        if (!subscriptionContainer) return;

        const subscription = data.subscription || {};
        const profile = data.profile || {};

        // Format details
        const planName = subscription.plan_name || 'Plan gratuit';
        const status = subscription.status || 'inactive';
        const statusLabel = status === 'active' ? 'Actif' : 'Inactif';
        const statusBadgeClass = status === 'active' ? 'bg-success' : 'bg-secondary';

        const leadsQuota = profile.leads_quota || 5;
        const leadsUsed = profile.leads_used || 0;
        const usagePercent = profile.unlimited_leads ? 0 : Math.min(Math.round((leadsUsed / leadsQuota) * 100), 100);

        // Create HTML for subscription info
        const html = `
            <div class="card mb-4">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">Votre abonnement actuel</h5>
                    <span class="badge ${statusBadgeClass}">${statusLabel}</span>
                </div>
                <div class="card-body">
                    <h4 class="mb-3">${planName}</h4>
                    
                    <div class="mb-3">
                        <label class="form-label">Utilisation des leads</label>
                        <div class="d-flex align-items-center">
                            ${profile.unlimited_leads ?
                '<span class="badge bg-success me-2">Illimité</span>' :
                `<div class="progress flex-grow-1 me-2" style="height: 8px;">
                                    <div class="progress-bar ${usagePercent > 80 ? 'bg-danger' : ''}" 
                                         role="progressbar" style="width: ${usagePercent}%" 
                                         aria-valuenow="${leadsUsed}" aria-valuemin="0" aria-valuemax="${leadsQuota}"></div>
                                </div>
                                <span>${leadsUsed} / ${leadsQuota}</span>`
            }
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Prix mensuel</label>
                        <div class="lead">${subscription.price || '0,00'} €</div>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Prochain paiement</label>
                        <div>${subscription.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : 'N/A'}</div>
                    </div>
                    
                    <div class="mt-4">
                        <a href="#billing-plans" class="btn btn-outline-primary">Gérer mon abonnement</a>
                    </div>
                </div>
            </div>
        `;

        subscriptionContainer.innerHTML = html;
    },

    /**
     * Fallback method to render plans directly to DOM
     * @param {Array} plans - Array of plan objects
     */
    renderPlansDirectly: function (plans) {
        const plansContainer = document.getElementById('availablePlans');
        if (!plansContainer || !plans || !plans.length) return;

        let plansHtml = '<div class="row">';

        plans.forEach(plan => {
            plansHtml += `
                <div class="col-md-4 mb-4">
                    <div class="card h-100">
                        <div class="card-header">
                            <h5 class="mb-0">${plan.name}</h5>
                        </div>
                        <div class="card-body d-flex flex-column">
                            <div class="price-tag mb-3">
                                <span class="display-5">${plan.price}€</span>
                                <span class="text-muted">/${plan.interval}</span>
                            </div>
                            
                            <div class="mb-3">
                                <span class="badge bg-primary">
                                    ${plan.leads_quota} leads par ${plan.interval}
                                </span>
                            </div>
                            
                            <ul class="list-unstyled mb-4">
                                ${plan.features.map(feature =>
                `<li class="mb-2">
                                        <i class="fas fa-check text-success me-2"></i> ${feature}
                                    </li>`
            ).join('')}
                            </ul>
                            
                            <button class="btn btn-primary mt-auto select-plan-btn" data-plan-id="${plan.id}">
                                Choisir ce plan
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });

        plansHtml += '</div>';
        plansContainer.innerHTML = plansHtml;

        // Add event listeners for plan selection
        document.querySelectorAll('.select-plan-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                if (typeof this.selectPlan === 'function') {
                    this.selectPlan(parseInt(btn.dataset.planId));
                }
            });
        });
    },
};

// Initialize module when DOM is fully loaded
document.addEventListener('DOMContentLoaded', function () {
    WizzyBilling.init();
}); 