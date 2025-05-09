/**
 * Wizzy Dashboard Overview Module
 * Displays user usage statistics and subscription information
 */

const WizzyDashboardOverview = {
    // Chart instances
    charts: {
        usageChart: null,
        weeklyLeadsChart: null
    },

    // Refresh interval ID
    refreshIntervalId: null,

    // Initialize the overview
    init: function () {
        console.log('Initializing dashboard overview');

        // Check authentication
        if (!WizzyUtils.isAuthenticated()) {
            return;
        }

        this.loadUsageData();
        this.loadSubscriptionData();

        // Set up auto-refresh every 60 seconds
        this.startAutoRefresh();

        // Clean up on page unload
        window.addEventListener('beforeunload', () => this.stopAutoRefresh());
    },

    // Start auto-refresh for dashboard data
    startAutoRefresh: function () {
        // Clear any existing interval first
        this.stopAutoRefresh();

        // Set a new refresh interval
        this.refreshIntervalId = setInterval(() => {
            console.log('Auto-refreshing dashboard data');
            this.loadUsageData();
            this.loadSubscriptionData();
        }, 60000); // 60 seconds refresh
    },

    // Stop auto-refresh
    stopAutoRefresh: function () {
        if (this.refreshIntervalId) {
            clearInterval(this.refreshIntervalId);
            this.refreshIntervalId = null;
        }
    },

    // Load usage data and statistics
    loadUsageData: async function () {
        try {
            // Add a cache-busting parameter to prevent caching
            const timestamp = new Date().getTime();
            const response = await WizzyUtils.apiRequest(`/api/dashboard/stats/?_=${timestamp}`);

            if (response.ok) {
                const data = await response.json();
                this.renderUsageStats(data);
                this.renderUsageCharts(data);
            } else {
                console.error('Failed to load usage data');
                WizzyUtils.showAlert('Erreur lors du chargement des statistiques d\'utilisation', 'danger');

                // Use placeholder data for development
                this.renderPlaceholderData();
            }
        } catch (error) {
            console.error('Error loading usage data:', error);
            WizzyUtils.showAlert('Erreur lors du chargement des données d\'utilisation', 'danger');

            // Use placeholder data for development
            this.renderPlaceholderData();
        }
    },

    // Load subscription data
    loadSubscriptionData: async function () {
        try {
            // Add a cache-busting parameter to prevent caching
            const timestamp = new Date().getTime();
            const response = await WizzyUtils.apiRequest(`/api/dashboard/subscription/?_=${timestamp}`);

            if (response.ok) {
                const data = await response.json();
                this.renderSubscriptionInfo(data);
                this.renderAvailablePlans(data.available_plans);
            } else {
                console.error('Failed to load subscription data');
                WizzyUtils.showAlert('Erreur lors du chargement des données d\'abonnement', 'danger');

                // Use placeholder data
                this.renderPlaceholderSubscriptionData();
            }
        } catch (error) {
            console.error('Error loading subscription data:', error);
            WizzyUtils.showAlert('Erreur lors du chargement des données d\'abonnement', 'danger');

            // Use placeholder data
            this.renderPlaceholderSubscriptionData();
        }
    },

    // Render usage statistics
    renderUsageStats: function (data) {
        const usageStats = document.getElementById('usageStats');
        if (!usageStats) return;

        // Get usage data
        const stats = data.usage_stats || {};
        const subscription = data.subscription || {};
        const leads = stats.leads_used || 0;
        const quota = stats.leads_quota || 5;
        const unlimited = stats.unlimited_leads || false;
        const rateLimited = stats.rate_limited_leads || 0;
        const incomplete = stats.incomplete_leads || 0;
        const isFreeUser = subscription?.plan?.name === 'Wizzy Free';

        // Format stats
        const usagePercent = unlimited ? 0 : Math.min(Math.round((leads / quota) * 100), 100);

        // Render HTML
        usageStats.innerHTML = `
            <div class="row">
                <div class="col-md-3">
                    <div class="card ${isFreeUser ? 'bg-light' : ''}">
                        <div class="card-body">
                            <h5 class="card-title">Leads utilisés</h5>
                            <div class="d-flex align-items-center">
                                <div class="display-4 me-3">${leads}</div>
                                <div>
                                    ${unlimited ?
                '<span class="badge bg-success">Illimité</span>' :
                `<small class="text-muted">sur ${quota}</small>
                                         <div class="progress mt-2" style="height: 8px;">
                                             <div class="progress-bar ${usagePercent > 80 ? 'bg-danger' : 'bg-primary'}" 
                                                  role="progressbar" style="width: ${usagePercent}%" 
                                                  aria-valuenow="${usagePercent}" aria-valuemin="0" aria-valuemax="100"></div>
                                         </div>`
            }
                                </div>
                            </div>
                            ${isFreeUser ? '<div class="mt-2"><small class="text-muted">Limite du plan gratuit</small></div>' : ''}
                        </div>
                    </div>
                </div>
                
                <div class="col-md-3">
                    <div class="card ${isFreeUser ? 'bg-light' : ''}">
                        <div class="card-body">
                            <h5 class="card-title">Structures actives</h5>
                            <div class="display-4">
                                ${stats.active_jobs || 0}
                            </div>
                            <small class="text-muted">sur ${stats.total_jobs || 0} total</small>
                            ${isFreeUser ? '<div class="mt-2"><small class="text-muted">Limite du plan gratuit</small></div>' : ''}
                        </div>
                    </div>
                </div>
                
                <div class="col-md-3">
                    <div class="card ${isFreeUser ? 'bg-light' : ''}">
                        <div class="card-body">
                            <h5 class="card-title">Leads trouvés</h5>
                            <div class="display-4">
                                ${stats.total_leads_found || 0}
                            </div>
                            <small class="text-muted">ce mois-ci</small>
                            ${isFreeUser ? '<div class="mt-2"><small class="text-muted">Limite du plan gratuit</small></div>' : ''}
                        </div>
                    </div>
                </div>
                
                <div class="col-md-3">
                    <div class="card ${isFreeUser ? 'bg-light' : ''}">
                        <div class="card-body">
                            <h5 class="card-title">Rate limités</h5>
                            <div class="display-4">
                                ${rateLimited}
                            </div>
                            <small class="text-muted">${incomplete} incomplets</small>
                            ${isFreeUser ? '<div class="mt-2"><small class="text-muted">Dépassement de quota</small></div>' : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    // Render usage charts
    renderUsageCharts: function (data) {
        // Render usage chart
        this.renderUsageChart(data);

        // Render weekly leads chart
        this.renderWeeklyLeadsChart(data);
    },

    // Render usage quota chart
    renderUsageChart: function (data) {
        const usageChartCanvas = document.getElementById('usageChart');
        if (!usageChartCanvas) return;

        // If chart already exists, destroy it
        if (this.charts.usageChart) {
            this.charts.usageChart.destroy();
        }

        // Get data
        const subscription = data.subscription || {};
        const leads = subscription.current_usage?.leads_used || 0;
        const quota = subscription.plan?.leads_quota || 0;
        const unlimited = subscription.plan?.unlimited_leads || false;

        // Set up data
        let chartData;
        if (unlimited) {
            chartData = {
                labels: ['Utilisation'],
                datasets: [{
                    data: [100],
                    backgroundColor: ['rgba(40, 167, 69, 0.8)'],
                    borderWidth: 0
                }]
            };
        } else {
            const remaining = Math.max(0, quota - leads);
            chartData = {
                labels: ['Utilisé', 'Restant'],
                datasets: [{
                    data: [leads, remaining],
                    backgroundColor: [
                        'rgba(0, 123, 255, 0.8)',
                        'rgba(233, 236, 239, 0.8)'
                    ],
                    borderWidth: 0
                }]
            };
        }

        // Create chart
        this.charts.usageChart = new Chart(usageChartCanvas, {
            type: 'doughnut',
            data: chartData,
            options: {
                cutout: '70%',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                return `${context.label}: ${context.raw}`;
                            }
                        }
                    },
                    doughnutlabel: {
                        labels: [{
                            text: unlimited ? 'Illimité' : `${leads}/${quota}`,
                            font: {
                                size: '20'
                            }
                        }]
                    }
                }
            }
        });
    },

    // Render weekly leads chart
    renderWeeklyLeadsChart: function (data) {
        const weeklyLeadsCanvas = document.getElementById('weeklyLeadsChart');
        if (!weeklyLeadsCanvas) return;

        // If chart already exists, destroy it
        if (this.charts.weeklyLeadsChart) {
            this.charts.weeklyLeadsChart.destroy();
        }

        // Get data
        const weeklyData = data.weekly_leads || [];

        // Process data for chart
        const labels = weeklyData.map(d => d.date);
        const values = weeklyData.map(d => d.leads);

        // Create chart
        this.charts.weeklyLeadsChart = new Chart(weeklyLeadsCanvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Leads générés',
                    data: values,
                    backgroundColor: 'rgba(0, 123, 255, 0.5)',
                    borderColor: 'rgba(0, 123, 255, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                return `${context.raw} leads`;
                            }
                        }
                    }
                }
            }
        });
    },

    // Render subscription information
    renderSubscriptionInfo: function (data) {
        const subscriptionInfo = document.getElementById('subscriptionInfo');
        if (!subscriptionInfo) return;

        // Get subscription data
        const subscription = data.subscription || {};
        const currentUsage = data.current_usage || {};
        const profile = data.profile || {};
        const isFreeUser = profile.role === 'free';

        // Format subscription details
        const planName = subscription.plan?.name || 'Plan gratuit';
        const leadsQuota = currentUsage.leads_quota || 5;
        const leadsUsed = currentUsage.leads_used || 0;
        const unlimited = currentUsage.unlimited_leads || false;
        const rateLimited = data.leads?.rate_limited || 0;
        const incomplete = data.leads?.incomplete || 0;

        // Calculate usage percentage
        const usagePercent = unlimited ? 0 : Math.min(Math.round((leadsUsed / leadsQuota) * 100), 100);

        // Render HTML
        subscriptionInfo.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h5 class="card-title mb-0">Votre abonnement</h5>
                </div>
                <div class="card-body">
                    <h4 class="mb-3">${planName}</h4>
                    
                    <div class="mb-3">
                        <label class="form-label">Quota de leads</label>
                        <div class="d-flex align-items-center">
                            ${unlimited ?
                '<span class="badge bg-success me-2">Illimité</span>' :
                `<div class="progress flex-grow-1 me-2" style="height: 8px;">
                                    <div class="progress-bar ${usagePercent > 80 ? 'bg-danger' : ''}" 
                                         role="progressbar" style="width: ${usagePercent}%" 
                                         aria-valuenow="${leadsUsed}" aria-valuemin="0" aria-valuemax="${leadsQuota}"></div>
                                </div>
                                <span>${leadsUsed} / ${leadsQuota}</span>`
            }
                        </div>
                        ${isFreeUser ? '<small class="text-muted">Limite du plan gratuit</small>' : ''}
                    </div>
                    
                    ${rateLimited > 0 ? `
                    <div class="mb-3 alert alert-warning py-2">
                        <label class="form-label mb-0">Leads rate limités</label>
                        <div class="d-flex align-items-center">
                            <span>${rateLimited} leads limités par votre quota</span>
                        </div>
                    </div>` : ''}
                    
                    <div class="mb-3">
                        <label class="form-label">Fonctionnalités incluses</label>
                        <ul class="list-group">
                            ${(subscription.plan?.features || []).map(feature =>
                `<li class="list-group-item ${isFreeUser ? 'bg-light' : ''}">
                                    <i class="fas fa-check text-success me-2"></i> ${feature}
                                </li>`
            ).join('')}
                        </ul>
                    </div>
                    
                    ${isFreeUser ? `
                        <div class="alert alert-info">
                            <h6 class="alert-heading">Débloquez tout le potentiel de Wizzy</h6>
                            <p class="mb-0">Passez à un plan supérieur pour accéder à plus de leads et de fonctionnalités.</p>
                        </div>
                    ` : ''}
                    
                    <a href="#billing" class="btn btn-outline-primary">
                        ${isFreeUser ? 'Passer à un plan supérieur' : 'Gérer mon abonnement'}
                    </a>
                </div>
            </div>
        `;
    },

    // Render available plans
    renderAvailablePlans: function (plans) {
        const availablePlans = document.getElementById('availablePlans');
        if (!availablePlans || !plans || !plans.length) return;

        // Create HTML for plans
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
                            
                            <button class="btn btn-primary mt-auto" 
                                    onclick="WizzyBilling.selectPlan(${plan.id})">
                                Choisir ce plan
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });

        plansHtml += '</div>';
        availablePlans.innerHTML = plansHtml;
    },

    // Render placeholder subscription data
    renderPlaceholderSubscriptionData: function () {
        // Placeholder subscription based on user role/plan
        let userPlan = 'free'; // Default to free

        // In a real implementation, this would come from the user data
        // For now, check if we can get it from the DOM
        const userRoleElement = document.querySelector('[data-user-role]');
        if (userRoleElement) {
            userPlan = userRoleElement.dataset.userRole;
        }

        // Subscription plans based on the provided information
        const plans = [
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
                price: 70,
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
                    'IA qui parle'
                ]
            },
            {
                id: 3,
                name: 'Wizzy Premium',
                price: 170,
                interval: 'mois',
                leads_quota: 150,
                unlimited_leads: false,
                features: [
                    'Scraping illimité (150/jour)',
                    'Maximum d\'informations (5-6)',
                    'Automatisation des messages personnalisés',
                    'Scraping de haute qualité sur tous les sites y compris les réseaux sociaux',
                    'Prompts personnalisés pour approcher les clients',
                    'Conseils personnalisés spécifiques à votre service/bien',
                    'IA qui parle',
                    'Équipe Closer qui va se charger de closer à votre place'
                ]
            }
        ];

        // Select the appropriate plan
        let userPlanIndex = 0;
        switch (userPlan) {
            case 'classic':
                userPlanIndex = 1;
                break;
            case 'premium':
                userPlanIndex = 2;
                break;
            default:
                userPlanIndex = 0; // Free
        }

        // Generate usage data based on plan
        const currentPlan = plans[userPlanIndex];
        let leadsUsed = 0;

        // Simulate some usage based on the subscription level
        if (userPlanIndex === 0) { // Free
            leadsUsed = Math.floor(Math.random() * 5);
        } else if (userPlanIndex === 1) { // Classic
            leadsUsed = Math.floor(Math.random() * 70) + 30; // Between 30-100
        } else if (userPlanIndex === 2) { // Premium
            leadsUsed = Math.floor(Math.random() * 100) + 50; // Between 50-150
        }

        // Create the data object
        const data = {
            subscription: {
                plan: currentPlan,
                current_usage: {
                    leads_used: leadsUsed,
                    structures_count: userPlanIndex === 0 ? 1 : (userPlanIndex === 1 ? 5 : 12),
                    active_structures: userPlanIndex === 0 ? 1 : (userPlanIndex === 1 ? 3 : 8)
                },
                start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(), // 30 days ago
                next_billing_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString() // 30 days from now
            },
            available_plans: plans
        };

        // Render with customized data
        this.renderSubscriptionInfo(data);
        this.renderAvailablePlans(data.available_plans);
    },

    // Render placeholder data for development when API is not available
    renderPlaceholderData: function () {
        // Get user plan data (as with subscription data)
        let userPlan = 'free'; // Default to free
        const userRoleElement = document.querySelector('[data-user-role]');
        if (userRoleElement) {
            userPlan = userRoleElement.dataset.userRole;
        }

        // Set statistics based on plan level
        let activeStructures = 1;
        let activeJobs = 0;
        let totalLeadsFound = 0;
        let leadsQuota = 5;
        let leadsUsed = 0;

        // Adjust based on plan
        switch (userPlan) {
            case 'classic':
                activeStructures = 5;
                activeJobs = 2;
                totalLeadsFound = 87;
                leadsQuota = 100;
                leadsUsed = Math.floor(Math.random() * 70) + 30;
                break;
            case 'premium':
                activeStructures = 12;
                activeJobs = 4;
                totalLeadsFound = 243;
                leadsQuota = 150;
                leadsUsed = Math.floor(Math.random() * 100) + 50;
                break;
            default: // free
                activeStructures = 1;
                activeJobs = 0;
                totalLeadsFound = 5;
                leadsQuota = 5;
                leadsUsed = Math.floor(Math.random() * 5);
        }

        // Generate weekly data with a trend based on plan
        const weeklyLeads = [];
        const today = new Date();
        for (let i = 6; i >= 0; i--) {
            const date = new Date(today);
            date.setDate(date.getDate() - i);

            // Generate leads based on plan
            let leads = 0;
            if (userPlan === 'free') {
                leads = Math.floor(Math.random() * 2);
            } else if (userPlan === 'classic') {
                leads = Math.floor(Math.random() * 15) + 5;
            } else { // premium
                leads = Math.floor(Math.random() * 25) + 15;
            }

            weeklyLeads.push({
                date: date.toISOString().split('T')[0],
                leads: leads
            });
        }

        // Create data object
        const data = {
            stats: {
                active_structures: activeStructures,
                active_jobs: activeJobs,
                total_leads_found: totalLeadsFound
            },
            subscription: {
                plan: {
                    name: userPlan === 'premium' ? 'Wizzy Premium' : (userPlan === 'classic' ? 'Wizzy Classique' : 'Wizzy Free'),
                    leads_quota: leadsQuota,
                    unlimited_leads: false,
                    features: []
                },
                current_usage: {
                    leads_used: leadsUsed
                }
            },
            weekly_leads: weeklyLeads
        };

        // Render with customized placeholder data
        this.renderUsageStats(data);
        this.renderUsageCharts(data);
    }
};

// Add event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    // Nothing to do here as initialization is handled by WizzyDashboard
}); 