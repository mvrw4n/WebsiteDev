/**
 * WizzyLeadsAndEnrichment - Module pour gérer les leads et l'enrichissement du profil
 * Permet d'afficher les leads collectés et de gérer les informations du profil utilisateur
 */
const WizzyIndustryEnrichment = (() => {
    // Configuration
    const config = {
        endpoints: {
            userProfile: '/api/user/profile/',
            userLeads: '/api/leads/',
            leadsStats: '/api/leads/stats/',
            leadDetail: '/api/leads/'
        },
        elements: {
            industryForm: '#industryForm',
            targetsForm: '#targetsForm',
            userLeadsContainer: '#userLeadsContainer',
            leadsTableBody: '#leadsTableBody',
            noLeadsMessage: '#noLeadsMessage',
            leadsTable: '#leadsTable',
            leadsFilterSelect: '#leadsFilterSelect',
            refreshLeadsBtn: '#refreshLeadsBtn',
            prevPageBtn: '#prevPageBtn',
            nextPageBtn: '#nextPageBtn',
            paginationInfo: '#paginationInfo',
            totalLeadsCount: '#totalLeadsCount',
            totalLeadsCollected: '#totalLeadsCollected',
            uniqueLeadsCount: '#uniqueLeadsCount',
            lastWeekLeadsCount: '#lastWeekLeadsCount',
            leadsDistributionChart: '#leadsDistributionChart',
            leadsTimelineChart: '#leadsTimelineChart',
            loadingSpinner: '.loading-spinner',
            errorMessage: '.error-message',
            leadDetailModal: '#leadDetailModal',
            leadDetailContent: '#leadDetailContent',
            profileWelcomePopup: '#profileWelcomePopup'
        },
        colors: {
            primary: '#FF8C00', // Couleur principale de Wizzy (orange)
            secondary: '#f8f9fa',
            text: '#333333',
            light: '#ffffff'
        }
    };

    // État
    let state = {
        userProfile: null,
        leads: [],
        leadsStats: null,
        isLoading: false,
        pagination: {
            currentPage: 1,
            totalPages: 1,
            perPage: 20
        },
        filter: 'all',
        charts: {
            distribution: null,
            timeline: null
        },
        profilePopupShown: false
    };

    // Ajouter un tag pour savoir si le popup a déjà été affiché
    const PROFILE_POPUP_SHOWN_FLAG = 'wizzy_profile_popup_shown';
    const PROFILE_POPUP_EXPIRY = 'wizzy_profile_popup_expiry'; // Pour réafficher après un certain temps

    // Fonction pour déterminer si on doit afficher le popup sur n'importe quelle page du dashboard
    const shouldShowWelcomePopup = () => {
        // Vérifier si le popup a déjà été affiché récemment
        const popupShown = localStorage.getItem(PROFILE_POPUP_SHOWN_FLAG) === 'true';
        const popupExpiry = localStorage.getItem(PROFILE_POPUP_EXPIRY);
        const now = new Date().getTime();

        // Si le popup n'a jamais été montré ou si la date d'expiration est dépassée
        if (!popupShown || (popupExpiry && parseInt(popupExpiry) < now)) {
            return true;
        }

        return false;
    };

    /**
     * Check if Bootstrap might be partially loaded (CSS but no JS)
     */
    const isBootstrapCssOnlyLoaded = () => {
        // Check if there are Bootstrap CSS classes in use but the JS is not available
        const bootstrapElements = document.querySelectorAll('.modal, .btn, .alert, .nav, .navbar');
        return bootstrapElements.length > 0 && typeof bootstrap === 'undefined';
    };

    /**
     * Attempt to dynamically load Bootstrap JS if needed
     */
    const loadBootstrapJs = () => {
        return new Promise((resolve, reject) => {
            if (typeof bootstrap !== 'undefined') {
                console.log('Bootstrap already loaded, skipping dynamic load');
                resolve(true);
                return;
            }

            console.log('Attempting to dynamically load Bootstrap JS');

            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js';
            script.integrity = 'sha384-ka7Sk0Gln4gmtz2MlQnikT1wXgYsOg+OMhuP+IlRH9sENBO0LRn5q+8nbTov4+1p';
            script.crossOrigin = 'anonymous';

            script.onload = () => {
                console.log('Bootstrap JS loaded successfully');
                resolve(true);
            };

            script.onerror = (error) => {
                console.error('Error loading Bootstrap JS:', error);
                reject(error);
            };

            document.head.appendChild(script);
        });
    };

    /**
     * Vérifie si le profil utilisateur est suffisamment rempli
     * @param {Object} profileData - Données du profil utilisateur
     * @returns {boolean} - True si le profil est suffisamment rempli, false sinon
     */
    const isProfileComplete = (profileData) => {
        if (!profileData || !profileData.user_details) {
            return false;
        }

        const userDetails = profileData.user_details;

        // Vérifier les champs principaux du profil - section 1 et 2
        const industryInfoFields = [
            userDetails.company_name,
            userDetails.contact_name,
            userDetails.contact_email,
            userDetails.industry,
            userDetails.product_type,
            userDetails.business_model
        ];

        // Vérifier si les données d'acquisition sont remplies - section 3 et 4
        const acquisitionFields = userDetails.acquisition_details && [
            userDetails.acquisition_details.main_acquisition_channel,
            userDetails.acquisition_details.marketing_tools && userDetails.acquisition_details.marketing_tools.length > 0,
            userDetails.acquisition_details.planned_optimizations && userDetails.acquisition_details.planned_optimizations.length > 0
        ];

        // Compter les champs remplis dans chaque section
        const industryFieldsCount = industryInfoFields.filter(field => field && field !== '').length;
        const acquisitionFieldsCount = acquisitionFields ? acquisitionFields.filter(field => field).length : 0;

        // Le profil est considéré complet si au moins 3 champs d'industrie sont remplis 
        // OU si au moins 2 champs d'acquisition sont remplis
        return industryFieldsCount >= 3 || acquisitionFieldsCount >= 2;
    };

    /**
     * Crée et affiche le popup de bienvenue pour compléter le profil
     * @param {boolean} forceShow - Forcer l'affichage même si déjà vu
     */
    const createProfileWelcomePopup = (forceShow = false) => {
        // Vérifier si le popup a déjà été affiché au cours de cette session
        if (state.profilePopupShown && !forceShow) {
            return;
        }

        // Ne pas montrer si déjà vu et pas encore expiré
        if (!forceShow && !shouldShowWelcomePopup()) {
            return;
        }

        // Marquer le popup comme affiché pour cette session
        state.profilePopupShown = true;

        // Supprimer un popup existant si présent
        const existingPopup = document.getElementById('profileWelcomePopup');
        if (existingPopup) {
            existingPopup.remove();
        }

        // Créer l'élément du popup
        const popupElement = document.createElement('div');
        popupElement.id = 'profileWelcomePopup';
        popupElement.className = 'profile-welcome-popup';
        popupElement.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.7);
            z-index: 9999;
            display: flex;
            align-items: center;
            justify-content: center;
        `;

        popupElement.innerHTML = `
            <div class="popup-content" style="
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 5px 20px rgba(0, 0, 0, 0.3);
                padding: 30px;
                max-width: 550px;
                width: 90%;
                text-align: center;
                position: relative;
                border-top: 5px solid ${config.colors.primary};
            ">
                <button id="closeProfilePopup" style="
                    position: absolute;
                    top: 10px;
                    right: 10px;
                    background: none;
                    border: none;
                    font-size: 24px;
                    cursor: pointer;
                    color: #999;
                ">&times;</button>
                
                <div style="margin-bottom: 20px;">
                    <img src="/static/img/wizzy_face.jpeg" alt="Wizzy Assistant" style="
                        width: 120px;
                        height: auto;
                        margin-bottom: 15px;
                        border-radius: 60px;
                        border: 3px solid ${config.colors.primary};
                    ">
                </div>
                
                <h3 style="
                    font-size: 24px;
                    margin-bottom: 15px;
                    color: ${config.colors.primary};
                    font-weight: bold;
                ">Bienvenue sur Wizzy!</h3>
                
                <p style="
                    font-size: 16px;
                    line-height: 1.6;
                    color: ${config.colors.text};
                    margin-bottom: 20px;
                ">
                    Pour optimiser votre expérience, veuillez d'abord compléter votre 
                    <strong>profil d'industrie</strong> et vos <strong>objectifs de scraping</strong>.
                    Cela nous aidera à mieux comprendre vos besoins et à personnaliser notre service.
                </p>
                
                <button id="goToProfileBtn" class="btn" style="
                    background-color: ${config.colors.primary};
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 5px;
                    font-size: 16px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: background-color 0.2s;
                    margin-bottom: 15px;
                ">Compléter mon profil</button>
                
                <p style="
                    font-size: 13px;
                    color: #777;
                    margin-top: 15px;
                ">
                    Ces informations nous aident à personnaliser votre expérience et à améliorer la qualité des données collectées.
                </p>
            </div>
        `;

        // Ajouter le popup au body
        document.body.appendChild(popupElement);

        // Ajouter les gestionnaires d'événements
        document.getElementById('closeProfilePopup').addEventListener('click', () => {
            document.getElementById('profileWelcomePopup').remove();

            // Définir une expiration pour le popup (1 jour)
            const expiry = new Date();
            expiry.setDate(expiry.getDate() + 1);
            localStorage.setItem(PROFILE_POPUP_SHOWN_FLAG, 'true');
            localStorage.setItem(PROFILE_POPUP_EXPIRY, expiry.getTime().toString());
        });

        document.getElementById('goToProfileBtn').addEventListener('click', () => {
            // Fermer le popup
            document.getElementById('profileWelcomePopup').remove();

            // Rediriger vers l'onglet Leads et Extraction
            navigateToProfileSection();

            // Stocker l'information que le popup a été vu 
            // Mais ne pas définir d'expiration pour encourager l'utilisateur à compléter son profil
            localStorage.setItem(PROFILE_POPUP_SHOWN_FLAG, 'true');
        });
    };

    /**
     * Naviguer vers la section de profil d'industrie
     */
    const navigateToProfileSection = () => {
        // Récupérer l'URL actuelle
        const currentUrl = window.location.href;
        const baseUrl = currentUrl.split('#')[0];

        // Si nous ne sommes pas sur la page dashboard, rediriger
        if (!currentUrl.includes('/dashboard')) {
            window.location.href = '/dashboard/#leads';
            return;
        }

        // Changer d'onglet si nécessaire (en utilisant les onglets de Bootstrap ou autre système)
        const leadsTab = document.querySelector('a[href="#leads"], button[data-bs-target="#leads"], [data-toggle="tab"][href="#leads"]');
        if (leadsTab) {
            // Utilisez la méthode appropriée pour activer l'onglet selon la version de Bootstrap
            if (typeof bootstrap !== 'undefined' && bootstrap.Tab) {
                const tab = new bootstrap.Tab(leadsTab);
                tab.show();
            } else if (typeof $ !== 'undefined' && $(leadsTab).tab) {
                $(leadsTab).tab('show');
            } else {
                // Fallback: simuler un clic et changer l'URL
                leadsTab.click();
                window.location.href = baseUrl + '#leads';
            }
        } else {
            // Si on ne trouve pas l'onglet, changer directement l'URL
            window.location.href = baseUrl + '#leads';
        }

        // Défiler jusqu'au formulaire de profil avec un délai pour laisser le temps au DOM de se mettre à jour
        setTimeout(() => {
            const industryForm = document.querySelector(config.elements.industryForm);
            if (industryForm) {
                industryForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }, 500);
    };

    /**
     * Initialisation du module
     */
    const init = async () => {
        console.log('Initializing leads and enrichment module...');

        // Check if Bootstrap might be partially loaded and try to load it if needed
        if (isBootstrapCssOnlyLoaded()) {
            console.log('Bootstrap CSS detected but JS missing, attempting to load Bootstrap JS');
            try {
                await loadBootstrapJs();
                console.log('Bootstrap JS loaded successfully');
            } catch (error) {
                console.error('Failed to load Bootstrap JS:', error);
            }
        }

        // Check if we have a proper authentication method
        let isAuthenticated = false;

        // Try with WizzyUtils
        if (typeof WizzyUtils !== 'undefined') {
            isAuthenticated = WizzyUtils.isAuthenticated();
            console.log('Authentication status (WizzyUtils):', isAuthenticated);
        }

        // Also try with AuthManager
        if (typeof AuthManager !== 'undefined') {
            isAuthenticated = isAuthenticated || AuthManager.isAuthenticated();
            console.log('Authentication status (AuthManager):', AuthManager.isAuthenticated());
        }

        // Fallback to checking localStorage directly
        if (!isAuthenticated) {
            isAuthenticated = !!localStorage.getItem('access_token');
            console.log('Authentication status (localStorage):', isAuthenticated);
        }

        if (!isAuthenticated) {
            console.warn('User not authenticated, displaying minimal interface');
            // Display a message in the leads container
            const leadsContainer = document.querySelector(config.elements.userLeadsContainer);
            if (leadsContainer) {
                leadsContainer.innerHTML = `
                    <div class="alert alert-warning">
                        <h5 class="alert-heading"><i class="fas fa-exclamation-triangle me-2"></i> Authentification requise</h5>
                        <p>Vous devez être connecté pour accéder à vos leads et à votre profil d'industrie.</p>
                        <hr>
                        <p class="mb-0">Veuillez <a href="/auth/login/?next=/dashboard/#leads" class="alert-link">vous connecter</a> pour continuer.</p>
                    </div>
                `;
            }
            return;
        }

        // Add event listeners first
        setupEventListeners();

        // Initialize charts
        initCharts();

        // Create the lead detail modal if it doesn't exist
        createLeadDetailModal();

        // Load data afterwards - wrapped in try/catch for safety
        try {
            const profileData = await loadUserProfile();
            if (profileData) {
                // Vérifier si le profil est complet
                if (!isProfileComplete(profileData)) {
                    // Si le profil n'est pas complet, afficher le popup de bienvenue
                    createProfileWelcomePopup();
                }

                // Only load leads and stats if we have a profile
                await loadUserLeads();
                await loadLeadsStats();
            } else {
                // Si pas de profil, afficher le popup également
                createProfileWelcomePopup();
            }
        } catch (err) {
            console.error('Error initializing module:', err);
            // Display error message to user
            if (typeof WizzyUtils !== 'undefined') {
                WizzyUtils.showAlert('Erreur de chargement des données. Veuillez rafraîchir la page.', 'danger');
            } else {
                showError('Erreur de chargement des données. Veuillez rafraîchir la page.');
            }
        }
    };

    /**
     * Configuration des écouteurs d'événements
     */
    const setupEventListeners = () => {
        // Formulaire d'industrie
        const industryForm = document.querySelector(config.elements.industryForm);
        if (industryForm) {
            industryForm.addEventListener('submit', function (e) {
                e.preventDefault();
                e.stopPropagation();
                saveIndustryProfile();
                return false;
            });
        }

        // Formulaire de cibles
        const targetsForm = document.querySelector(config.elements.targetsForm);
        if (targetsForm) {
            targetsForm.addEventListener('submit', function (e) {
                e.preventDefault();
                e.stopPropagation();
                saveTargets();
                return false;
            });
        }

        // Bouton de rafraîchissement des leads
        const refreshBtn = document.querySelector(config.elements.refreshLeadsBtn);
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                loadUserLeads();
            });
        }

        // Filtre des leads
        const filterSelect = document.querySelector(config.elements.leadsFilterSelect);
        if (filterSelect) {
            filterSelect.addEventListener('change', () => {
                state.filter = filterSelect.value;
                state.pagination.currentPage = 1;
                loadUserLeads();
            });
        }

        // Pagination
        const prevBtn = document.querySelector(config.elements.prevPageBtn);
        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (state.pagination.currentPage > 1) {
                    state.pagination.currentPage--;
                    loadUserLeads();
                }
            });
        }

        const nextBtn = document.querySelector(config.elements.nextPageBtn);
        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (state.pagination.currentPage < state.pagination.totalPages) {
                    state.pagination.currentPage++;
                    loadUserLeads();
                }
            });
        }
    };

    /**
     * Obtenir le token CSRF
     */
    const getCsrfToken = () => {
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];

        return cookieValue || '';
    };

    /**
     * Afficher ou masquer l'indicateur de chargement
     */
    const showLoading = (show = true) => {
        const spinners = document.querySelectorAll(config.elements.loadingSpinner);
        spinners.forEach(spinner => {
            spinner.style.display = show ? 'block' : 'none';
        });

        // Add loading class to body for global styling
        if (show) {
            document.body.classList.add('is-loading');
        } else {
            document.body.classList.remove('is-loading');
        }
    };

    /**
     * Afficher un message d'erreur
     */
    const showError = (message) => {
        const errorElements = document.querySelectorAll(config.elements.errorMessage);

        errorElements.forEach(element => {
            element.textContent = message;
            element.style.display = 'block';

            // Auto-hide after 5 seconds
            setTimeout(() => {
                element.style.display = 'none';
            }, 5000);
        });

        // If no error elements found, try to use WizzyUtils or create an alert
        if (errorElements.length === 0) {
            if (typeof WizzyUtils !== 'undefined') {
                WizzyUtils.showAlert(message, 'danger');
            } else {
                // Create a temporary error message
                const tempError = document.createElement('div');
                tempError.className = 'alert alert-danger';
                tempError.textContent = message;
                tempError.style.position = 'fixed';
                tempError.style.top = '20px';
                tempError.style.right = '20px';
                tempError.style.zIndex = '9999';

                document.body.appendChild(tempError);

                // Auto-remove after 5 seconds
                setTimeout(() => {
                    tempError.remove();
                }, 5000);
            }
        }

        console.error('Error:', message);
    };

    /**
     * Afficher un message de succès
     */
    const showSuccess = (message) => {
        // Créer un élément de toast pour le message de succès
        const toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            // Créer le conteneur de toast s'il n'existe pas
            const newContainer = document.createElement('div');
            newContainer.id = 'toast-container';
            newContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            document.body.appendChild(newContainer);
        }

        const container = document.getElementById('toast-container');
        const toastId = 'success-toast-' + Date.now();

        const toastHtml = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header bg-success text-white">
                    <strong class="me-auto">Succès</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', toastHtml);

        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
        toast.show();

        // Supprimer l'élément après qu'il soit masqué
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    };

    /**
     * Charger le profil utilisateur depuis l'API - now returns a promise for chaining
     */
    const loadUserProfile = async () => {
        state.isLoading = true;
        showLoading(true);

        console.log('Loading user profile using AuthManager.fetchWithAuth...');

        try {
            // Use AuthManager's fetchWithAuth which handles token refresh and authentication properly
            let response;

            if (typeof AuthManager !== 'undefined' && typeof AuthManager.fetchWithAuth === 'function') {
                // Use AuthManager if available
                response = await AuthManager.fetchWithAuth(config.endpoints.userProfile);
            } else if (typeof WizzyUtils !== 'undefined' && typeof WizzyUtils.apiRequest === 'function') {
                // Fallback to WizzyUtils if available
                response = await WizzyUtils.apiRequest(config.endpoints.userProfile);
            } else {
                // Manual fallback if neither is available
                const token = localStorage.getItem('access_token');
                const csrfToken = getCsrfToken();

                response = await fetch(config.endpoints.userProfile, {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                    },
                    credentials: 'same-origin' // Include cookies
                });
            }

            console.log('Load profile response status:', response.status);

            // Handle 401 Unauthorized error specifically
            if (response.status === 401) {
                console.log('Authentication required for user profile. Using empty profile data.');

                // Update UI to show login required
                const leadsContainer = document.querySelector(config.elements.userLeadsContainer);
                if (leadsContainer) {
                    leadsContainer.innerHTML = `
                        <div class="alert alert-warning">
                            <h5 class="alert-heading"><i class="fas fa-exclamation-triangle me-2"></i> Authentification requise</h5>
                            <p>Vous devez être connecté pour accéder à vos leads et à votre profil d'industrie.</p>
                            <hr>
                            <p class="mb-0">Veuillez <a href="/auth/login/?next=/dashboard/#leads" class="alert-link">vous connecter</a> pour continuer.</p>
                        </div>
                    `;
                }

                showError('Vous devez être connecté pour accéder à votre profil.');

                // Return an empty profile so the UI doesn't break
                return null;
            }

            if (!response.ok) {
                throw new Error('Erreur lors du chargement du profil');
            }

            const data = await response.json();
            console.log('User profile data loaded successfully:', data);

            // Populate the profile data to state
            state.userProfile = data;

            // Populate form fields with user profile data
            if (data && data.user_details) {
                console.log('Populating forms with user details data');
                populateProfileForm(data);
            } else {
                console.warn('No user_details found in profile data');
            }

            // Hide loading indicators
            state.isLoading = false;
            showLoading(false);

            return data;
        } catch (error) {
            console.error('Error loading user profile:', error);
            state.isLoading = false;
            showLoading(false);
            showError('Erreur lors du chargement du profil');
            return null;
        }
    };

    /**
     * Remplir les formulaires avec les données du profil utilisateur
     */
    const populateProfileForm = (profileData) => {
        console.log('Populating forms with profile data:', profileData);

        if (!profileData) return;

        // Extract user_details which contains the form data
        const userDetails = profileData.user_details || {};
        console.log('User details for form population:', userDetails);

        // Populate industry form fields (section 1 et 2)
        const industryForm = document.querySelector(config.elements.industryForm);
        if (industryForm) {
            // Direct mappings from user_details to form fields
            const mappings = {
                'company_name': 'company_name',
                'contact_name': 'contact_name',
                'contact_email': 'contact_email',
                'contact_phone': 'contact_phone',
                'website': 'website',
                'industry': 'industry',
                'product_type': 'product_type',
                'average_price': 'average_price',
                'average_margin': 'average_margin',
                'business_model': 'business_model'
            };

            // Apply mappings
            for (const [formField, dataField] of Object.entries(mappings)) {
                const input = industryForm.querySelector(`[name="${formField}"]`);
                if (input && userDetails[dataField] !== undefined) {
                    input.value = userDetails[dataField] || '';
                    console.log(`Set ${formField} to ${userDetails[dataField]}`);
                }
            }
        }

        // Populate targets form fields (section 3 et 4)
        const targetsForm = document.querySelector(config.elements.targetsForm);
        if (targetsForm) {
            const acquisitionDetails = userDetails.acquisition_details || {};

            // Champs simples (textes et select uniques)
            const simpleFields = {
                'main_acquisition_channel': acquisitionDetails.main_acquisition_channel,
                'conversion_rate': acquisitionDetails.conversion_rate,
                'ad_budget': acquisitionDetails.ad_budget,
                'revenue_target': acquisitionDetails.revenue_target,
                'new_customers_target': acquisitionDetails.new_customers_target,
                'specific_needs': acquisitionDetails.specific_needs
            };

            // Appliquer les champs simples
            for (const [formField, value] of Object.entries(simpleFields)) {
                const input = targetsForm.querySelector(`[name="${formField}"]`);
                if (input && value !== undefined) {
                    input.value = value || '';
                }
            }

            // Traiter les sélections multiples
            const multiSelects = {
                'marketing_tools': acquisitionDetails.marketing_tools || [],
                'planned_optimizations': acquisitionDetails.planned_optimizations || []
            };

            // Appliquer les sélections multiples
            for (const [selectName, values] of Object.entries(multiSelects)) {
                const select = targetsForm.querySelector(`[name="${selectName}"]`);
                if (select && Array.isArray(values)) {
                    Array.from(select.options).forEach(option => {
                        option.selected = values.includes(option.value);
                    });
                }
            }
        }

        console.log('Forms populated successfully');
    };

    /**
     * Sauvegarder le profil d'industrie
     */
    const saveIndustryProfile = () => {
        const form = document.querySelector(config.elements.industryForm);
        if (!form) return;

        // Récupérer les valeurs du formulaire - section 1 et 2
        const companyName = form.querySelector('[name="company_name"]').value;
        const contactName = form.querySelector('[name="contact_name"]').value;
        const contactEmail = form.querySelector('[name="contact_email"]').value;
        const contactPhone = form.querySelector('[name="contact_phone"]').value;
        const website = form.querySelector('[name="website"]').value;
        const industry = form.querySelector('[name="industry"]').value;
        const productType = form.querySelector('[name="product_type"]').value;
        const averagePrice = form.querySelector('[name="average_price"]').value;
        const averageMargin = form.querySelector('[name="average_margin"]').value;
        const businessModel = form.querySelector('[name="business_model"]').value;

        console.log('Saving industry profile data:', {
            companyName, contactName, contactEmail, contactPhone, website,
            industry, productType, averagePrice, averageMargin, businessModel
        });

        // Get existing user_details or initialize empty object
        const existingDetails = state.userProfile && state.userProfile.user_details ?
            { ...state.userProfile.user_details } : {};

        // Créer l'objet de données à envoyer
        const userDetails = {
            ...existingDetails,
            company_name: companyName,
            contact_name: contactName,
            contact_email: contactEmail,
            contact_phone: contactPhone,
            website: website,
            industry: industry,
            product_type: productType,
            average_price: averagePrice,
            average_margin: averageMargin,
            business_model: businessModel
        };

        // Envoyer les données à l'API
        updateUserProfile({ user_details: userDetails });
    };

    /**
     * Sauvegarder les cibles et objectifs
     */
    const saveTargets = () => {
        const form = document.querySelector(config.elements.targetsForm);
        if (!form) return;

        // Récupérer les valeurs du formulaire - section 3 et 4
        // Champs simples
        const mainAcquisitionChannel = form.querySelector('[name="main_acquisition_channel"]') ?
            form.querySelector('[name="main_acquisition_channel"]').value : '';
        const conversionRate = form.querySelector('[name="conversion_rate"]') ?
            form.querySelector('[name="conversion_rate"]').value : '';
        const adBudget = form.querySelector('[name="ad_budget"]') ?
            form.querySelector('[name="ad_budget"]').value : '';
        const revenueTarget = form.querySelector('[name="revenue_target"]') ?
            form.querySelector('[name="revenue_target"]').value : '';
        const newCustomersTarget = form.querySelector('[name="new_customers_target"]') ?
            form.querySelector('[name="new_customers_target"]').value : '';

        // Champs multi-sélection
        const marketingToolsSelect = form.querySelector('[name="marketing_tools"]');
        let marketingTools = [];
        if (marketingToolsSelect && marketingToolsSelect.selectedOptions) {
            marketingTools = Array.from(marketingToolsSelect.selectedOptions).map(opt => opt.value);
        }

        const plannedOptimizationsSelect = form.querySelector('[name="planned_optimizations"]');
        let plannedOptimizations = [];
        if (plannedOptimizationsSelect && plannedOptimizationsSelect.selectedOptions) {
            plannedOptimizations = Array.from(plannedOptimizationsSelect.selectedOptions).map(opt => opt.value);
        }

        // Get specific needs
        const specificNeeds = form.querySelector('[name="specific_needs"]') ?
            form.querySelector('[name="specific_needs"]').value : '';

        console.log('Saving acquisition & objectives data:', {
            mainAcquisitionChannel, conversionRate, adBudget,
            revenueTarget, newCustomersTarget,
            marketingTools, plannedOptimizations, specificNeeds
        });

        // Obtenir les détails utilisateur existants pour ne pas écraser d'autres données
        const existingDetails = state.userProfile && state.userProfile.user_details ?
            { ...state.userProfile.user_details } : {};

        // Get existing acquisition_details or initialize empty object
        const existingAcquisitionDetails = existingDetails.acquisition_details || {};

        // Mettre à jour les données d'acquisition et objectifs
        const updatedUserDetails = {
            ...existingDetails,
            acquisition_details: {
                ...existingAcquisitionDetails,
                main_acquisition_channel: mainAcquisitionChannel,
                conversion_rate: conversionRate,
                ad_budget: adBudget,
                revenue_target: revenueTarget,
                new_customers_target: newCustomersTarget,
                marketing_tools: marketingTools,
                planned_optimizations: plannedOptimizations,
                specific_needs: specificNeeds
            }
        };

        console.log('Saving acquisition data, full user_details:', updatedUserDetails);

        // Envoyer les données à l'API
        updateUserProfile({ user_details: updatedUserDetails });
    };

    /**
     * Mettre à jour le profil utilisateur
     */
    const updateUserProfile = async (profileData) => {
        state.isLoading = true;
        showLoading(true);

        console.log('DEBUG: Updating profile with method POST');
        console.log('Profile data being sent:', profileData);

        try {
            console.log('Updating user profile using AuthManager.fetchWithAuth...');

            // Use AuthManager if available, with fallbacks
            let response;
            if (typeof AuthManager !== 'undefined' && typeof AuthManager.fetchWithAuth === 'function') {
                console.log('DEBUG: Using AuthManager.fetchWithAuth with POST method');
                response = await AuthManager.fetchWithAuth(config.endpoints.userProfile, {
                    method: 'POST', // CONFIRMED POST
                    body: JSON.stringify(profileData)
                });
            } else if (typeof WizzyUtils !== 'undefined' && typeof WizzyUtils.apiRequest === 'function') {
                console.log('DEBUG: Using WizzyUtils.apiRequest with POST method');
                response = await WizzyUtils.apiRequest(config.endpoints.userProfile, {
                    method: 'POST', // CONFIRMED POST
                    body: JSON.stringify(profileData)
                });
            } else {
                // Manual fallback
                console.log('DEBUG: Using direct fetch with POST method');
                const token = localStorage.getItem('access_token');
                const csrfToken = getCsrfToken();

                response = await fetch(config.endpoints.userProfile, {
                    method: 'POST', // CONFIRMED POST
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                    },
                    body: JSON.stringify(profileData),
                    credentials: 'same-origin'
                });
            }

            // Handle unauthorized error
            if (response.status === 401) {
                console.log('Authentication required to update user profile');
                showError('Vous devez être connecté pour mettre à jour votre profil.');
                return { success: false };
            }

            if (!response.ok) {
                throw new Error('Erreur lors de la mise à jour du profil');
            }

            const data = await response.json();
            console.log('User profile updated successfully:', data);

            // Update state with new profile data
            if (data.profile) {
                state.userProfile = data.profile;

                // Repopulate forms with the updated profile data
                populateProfileForm(data.profile);
            } else if (data.success && profileData.user_details) {
                // If we don't get back a full profile but the update was successful,
                // update our local state with the data we sent
                if (!state.userProfile) {
                    state.userProfile = {};
                }
                state.userProfile.user_details = {
                    ...(state.userProfile.user_details || {}),
                    ...profileData.user_details
                };

                console.log('Updated local profile state:', state.userProfile);
                populateProfileForm(state.userProfile);
            }

            // Show success message
            if (typeof WizzyUtils !== 'undefined') {
                WizzyUtils.showAlert('Profil mis à jour avec succès.', 'success');
            } else {
                // Show embedded success message
                const successMsg = document.createElement('div');
                successMsg.className = 'alert alert-success mt-3';
                successMsg.textContent = 'Profil mis à jour avec succès.';

                const form = document.querySelector(config.elements.industryForm);
                if (form) {
                    form.appendChild(successMsg);
                    setTimeout(() => {
                        successMsg.remove();
                    }, 5000);
                }
            }

            // Reload stats as they may be affected by profile changes
            await loadLeadsStats();

            return { success: true, data };
        } catch (error) {
            console.error('Error updating user profile:', error);
            showError('Erreur lors de la mise à jour du profil');
            return { success: false };
        } finally {
            state.isLoading = false;
            showLoading(false);
        }
    };

    /**
     * Charger les leads de l'utilisateur
     */
    const loadUserLeads = async (filter = 'all', page = 1) => {
        state.isLoading = true;
        state.filter = filter;
        state.pagination.currentPage = page;
        showLoading(true);

        try {
            console.log('Loading user leads with filter:', filter, 'page:', page);

            // Build query parameters
            let queryParams = `?offset=${(page - 1) * state.pagination.perPage}&limit=${state.pagination.perPage}`;

            // Add filter parameters
            if (filter === 'recent') {
                // Last 7 days filter
                const sevenDaysAgo = new Date();
                sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
                queryParams += '&created_after=' + sevenDaysAgo.toISOString().split('T')[0];
            } else if (filter === 'not_contacted') {
                queryParams += '&status=not_contacted';
            } else if (filter === 'contacted') {
                queryParams += '&status=contacted';
            }

            // Make API request
            const response = await AuthManager.fetchWithAuth(config.endpoints.userLeads + queryParams);

            if (!response.ok) {
                throw new Error('Erreur lors du chargement des leads');
            }

            const data = await response.json();
            console.log('User leads loaded successfully:', data);

            // Store leads in state
            state.leads = data.results || [];

            // Update pagination
            state.pagination.totalPages = Math.ceil(data.count / state.pagination.perPage);

            // Render leads table
            renderLeadsTable(state.leads);

            // Update pagination controls
            updatePaginationControls();

            return state.leads;
        } catch (error) {
            console.error('Error loading user leads:', error);
            showError('Erreur lors du chargement des leads');
            return [];
        } finally {
            state.isLoading = false;
            showLoading(false);
        }
    };

    /**
     * Charger les statistiques des leads
     */
    const loadLeadsStats = async () => {
        showLoading(true);

        try {
            console.log('Loading leads statistics using AuthManager.fetchWithAuth...');

            // Use AuthManager if available, with fallbacks
            let response;
            if (typeof AuthManager !== 'undefined' && typeof AuthManager.fetchWithAuth === 'function') {
                response = await AuthManager.fetchWithAuth(config.endpoints.leadsStats);
            } else if (typeof WizzyUtils !== 'undefined' && typeof WizzyUtils.apiRequest === 'function') {
                response = await WizzyUtils.apiRequest(config.endpoints.leadsStats);
            } else {
                // Manual fallback
                const token = localStorage.getItem('access_token');
                const csrfToken = getCsrfToken();

                response = await fetch(config.endpoints.leadsStats, {
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

            // Handle unauthorized error
            if (response.status === 401) {
                console.log('Authentication required for leads statistics');
                // Return empty stats to avoid breaking the UI
                return {
                    total: 0,
                    unique: 0,
                    last_week: 0,
                    distribution: {},
                    timeline: {}
                };
            }

            if (!response.ok) {
                throw new Error('Erreur lors du chargement des statistiques');
            }

            const data = await response.json();
            console.log('Leads statistics loaded successfully');

            // Store stats data
            state.leadsStats = data;

            // Update stats counters
            updateLeadsCounters(data);

            // Update charts if they exist
            if (state.charts.distribution) {
                updateDistributionChart(data.distribution || {});
            }

            if (state.charts.timeline) {
                updateTimelineChart(data.timeline || {});
            }

            return data;
        } catch (error) {
            console.error('Error loading leads statistics:', error);
            showError('Erreur lors du chargement des statistiques');
            return null;
        } finally {
            showLoading(false);
        }
    };

    /**
     * Initialiser les graphiques de statistiques
     */
    const initCharts = () => {
        // Graphique de distribution des leads
        const distributionCtx = document.getElementById(config.elements.leadsDistributionChart.substring(1));
        if (distributionCtx) {
            state.charts.distribution = new Chart(distributionCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Traités', 'Non traités', 'Doublons'],
                    datasets: [{
                        data: [0, 0, 0],
                        backgroundColor: ['#28a745', '#007bff', '#6c757d']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }

        // Graphique d'évolution dans le temps
        const timelineCtx = document.getElementById(config.elements.leadsTimelineChart.substring(1));
        if (timelineCtx) {
            state.charts.timeline = new Chart(timelineCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Leads collectés',
                        data: [],
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
                        tension: 0.3,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        }
                    }
                }
            });
        }
    };

    /**
     * Mettre à jour le graphique de distribution
     */
    const updateDistributionChart = (distributionData) => {
        if (!state.charts.distribution) return;

        try {
            // Extract labels and data from distribution object
            const labels = Object.keys(distributionData) || [];
            const data = Object.values(distributionData) || [];

            // Update chart data
            state.charts.distribution.data.labels = labels;
            state.charts.distribution.data.datasets[0].data = data;

            // Apply random colors if needed
            if (!state.charts.distribution.data.datasets[0].backgroundColor ||
                state.charts.distribution.data.datasets[0].backgroundColor.length !== labels.length) {
                state.charts.distribution.data.datasets[0].backgroundColor = labels.map(() =>
                    `rgba(${Math.floor(Math.random() * 255)}, ${Math.floor(Math.random() * 255)}, ${Math.floor(Math.random() * 255)}, 0.7)`
                );
            }

            // Update the chart
            state.charts.distribution.update();
            console.log('Distribution chart updated with data:', distributionData);
        } catch (error) {
            console.error('Error updating distribution chart:', error);
        }
    };

    /**
     * Mettre à jour le graphique de timeline
     */
    const updateTimelineChart = (timelineData) => {
        if (!state.charts.timeline) return;

        try {
            // Extract dates and counts from timeline data
            const dates = Object.keys(timelineData) || [];
            const counts = Object.values(timelineData) || [];

            // Format dates for display
            const formattedDates = dates.map(dateStr => {
                const date = new Date(dateStr);
                return `${date.getDate()}/${date.getMonth() + 1}`;
            });

            // Update chart data
            state.charts.timeline.data.labels = formattedDates;
            state.charts.timeline.data.datasets[0].data = counts;

            // Update the chart
            state.charts.timeline.update();
            console.log('Timeline chart updated with data:', timelineData);
        } catch (error) {
            console.error('Error updating timeline chart:', error);
        }
    };

    /**
     * Mettre à jour les graphiques avec les statistiques
     */
    const updateCharts = () => {
        if (!state.leadsStats) return;

        // Mettre à jour le graphique de distribution
        if (state.charts.distribution) {
            state.charts.distribution.data.datasets[0].data = [
                state.leadsStats.processed_count || 0,
                state.leadsStats.unprocessed_count || 0,
                state.leadsStats.duplicate_count || 0
            ];
            state.charts.distribution.update();
        }

        // Mettre à jour le graphique d'évolution
        if (state.charts.timeline && state.leadsStats.timeline) {
            const labels = [];
            const data = [];

            for (const entry of state.leadsStats.timeline) {
                labels.push(entry.date);
                data.push(entry.count);
            }

            state.charts.timeline.data.labels = labels;
            state.charts.timeline.data.datasets[0].data = data;
            state.charts.timeline.update();
        }
    };

    /**
     * Mettre à jour les compteurs de leads
     */
    const updateLeadsCounters = (data) => {
        if (!data) return;

        const totalEl = document.querySelector(config.elements.totalLeadsCollected);
        if (totalEl) {
            totalEl.textContent = data.total_count || 0;
        }

        const uniqueEl = document.querySelector(config.elements.uniqueLeadsCount);
        if (uniqueEl) {
            uniqueEl.textContent = (data.total_count - data.duplicate_count) || 0;
        }

        const lastWeekEl = document.querySelector(config.elements.lastWeekLeadsCount);
        if (lastWeekEl) {
            lastWeekEl.textContent = data.last_week_count || 0;
        }
    };

    /**
     * Afficher les leads dans le tableau
     */
    const renderLeadsTable = (leads) => {
        const tableBody = document.querySelector(config.elements.leadsTableBody);
        const noLeadsMessage = document.querySelector(config.elements.noLeadsMessage);
        const leadsTable = document.querySelector(config.elements.leadsTable);

        if (!tableBody) return;

        // Clear existing rows
        tableBody.innerHTML = '';

        // Show or hide based on leads availability
        if (!leads || leads.length === 0) {
            if (noLeadsMessage) noLeadsMessage.classList.remove('d-none');
            if (leadsTable) leadsTable.classList.add('d-none');
            return;
        }

        // Show table, hide empty message
        if (noLeadsMessage) noLeadsMessage.classList.add('d-none');
        if (leadsTable) leadsTable.classList.remove('d-none');

        // Render each lead
        leads.forEach(lead => {
            const row = document.createElement('tr');

            // Format the date
            const createdDate = new Date(lead.created_at);
            const formattedDate = createdDate.toLocaleDateString('fr-FR', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            });

            // Determine the status badge style
            let statusBadgeClass = 'bg-secondary';
            if (lead.status === 'contacted') {
                statusBadgeClass = 'bg-primary';
            } else if (lead.status === 'interested') {
                statusBadgeClass = 'bg-success';
            } else if (lead.status === 'not_interested') {
                statusBadgeClass = 'bg-danger';
            } else if (lead.status === 'converted') {
                statusBadgeClass = 'bg-warning text-dark';
            }

            // Build contact info
            let contactInfo = '';
            if (lead.email && lead.email !== 'None' && lead.email !== 'null') {
                contactInfo += `<div><i class="fas fa-envelope me-1"></i> ${lead.email}</div>`;
            }
            if (lead.phone && lead.phone !== 'None' && lead.phone !== 'null') {
                contactInfo += `<div><i class="fas fa-phone me-1"></i> ${lead.phone}</div>`;
            }

            // Add the lead status badge
            const statusBadge = `<span class="badge ${statusBadgeClass}">${lead.status_display || lead.status}</span>`;

            // Get entity name from the first field of custom structure if available
            let primaryEntityName = '';

            // If lead has data and it's an object with values
            if (lead.data && typeof lead.data === 'object' && Object.keys(lead.data).length > 0) {
                // Get first field from the data (structure's first field)
                const firstFieldKey = Object.keys(lead.data)[0];
                if (firstFieldKey && lead.data[firstFieldKey] &&
                    lead.data[firstFieldKey] !== 'None' &&
                    lead.data[firstFieldKey] !== 'null') {
                    primaryEntityName = lead.data[firstFieldKey];
                }
            }

            // Fall back to company or name if no primary entity name from structure
            if (!primaryEntityName) {
                // Get name and company, handling possible None/Unknown values
                const displayName = lead.name && lead.name !== 'Unknown' && lead.name !== 'None' ? lead.name : '';
                const displayCompany = lead.company && lead.company !== 'None' && lead.company !== 'null' ? lead.company : '';
                primaryEntityName = displayCompany || displayName || 'Sans nom';
            }

            // Secondary display - use name if company was used as primary
            let secondaryDisplay = '';
            if (primaryEntityName === lead.company && lead.name && lead.name !== 'Unknown' && lead.name !== 'None') {
                secondaryDisplay = lead.name;
            } else if (!lead.company || lead.company === 'None' || lead.company === 'null') {
                secondaryDisplay = 'Sans entreprise';
            }

            // Create the cells
            row.innerHTML = `
                <td>
                    <div class="d-flex align-items-center">
                        <div>
                            <div class="fw-bold">${primaryEntityName}</div>
                            <div class="text-muted small">${secondaryDisplay}</div>
                            <div class="mt-1">${statusBadge}</div>
                        </div>
                    </div>
                </td>
                <td>${contactInfo || '<span class="text-muted">Aucun contact</span>'}</td>
                <td>${lead.source || 'Scraping'}</td>
                <td>${formattedDate}</td>
                <td>
                    <div class="btn-group">
                        <button class="btn btn-sm btn-outline-primary view-lead-btn" data-lead-id="${lead.id}" title="Voir les détails">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-success mark-contacted-btn" data-lead-id="${lead.id}" title="Marquer comme contacté">
                            <i class="fas fa-check"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger mark-not-interested-btn" data-lead-id="${lead.id}" title="Marquer comme pas intéressé">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </td>
            `;

            // Add the row to the table
            tableBody.appendChild(row);
        });

        // Set up event handlers for new elements
        setupLeadActionButtons();
    };

    /**
     * Configuration des boutons d'action pour les leads
     */
    const setupLeadActionButtons = () => {
        // Boutons pour visualiser un lead
        document.querySelectorAll('.view-lead-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const leadId = btn.dataset.leadId;
                console.log('Afficher les détails du lead:', leadId);
                showLeadDetails(leadId);
            });
        });

        // Boutons pour marquer comme contacté
        document.querySelectorAll('.mark-contacted-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const leadId = btn.dataset.leadId;
                updateLeadStatus(leadId, 'contacted');
            });
        });

        // Boutons pour marquer comme pas intéressé
        document.querySelectorAll('.mark-not-interested-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const leadId = btn.dataset.leadId;
                updateLeadStatus(leadId, 'not_interested');
            });
        });
    };

    /**
     * Mettre à jour le statut d'un lead
     */
    const updateLeadStatus = async (leadId, status) => {
        try {
            showLoading(true);

            const response = await AuthManager.fetchWithAuth('/api/leads/status-update/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    lead_ids: [leadId],
                    status: status
                })
            });

            if (!response.ok) {
                throw new Error(`Erreur lors de la mise à jour du statut: ${response.status}`);
            }

            const result = await response.json();
            console.log('Statut mis à jour avec succès:', result);

            // Afficher un message de succès
            showSuccess(`${result.updated_count} lead(s) mis à jour avec succès`);

            // Recharger les leads pour afficher les modifications
            await loadUserLeads(state.filter, state.pagination.currentPage);

        } catch (error) {
            console.error('Erreur lors de la mise à jour du statut:', error);
            showError('Impossible de mettre à jour le statut du lead');
        } finally {
            showLoading(false);
        }
    };

    /**
     * Show Lead Details - Direct HTML/DOM Implementation
     */
    const showLeadDetails = (leadId) => {
        console.log("🚀 DIRECT LEAD DETAILS FOR ID:", leadId);

        // STEP 1: Create popup via direct DOM - most reliable way
        const popupId = `lead-popup-${Date.now()}-${leadId}`;
        const detailsId = `lead-details-${Date.now()}-${leadId}`;

        // Remove any existing popups to prevent stacking
        document.querySelectorAll('[id^="lead-popup-"]').forEach(el => el.remove());

        // Create popup with inline styles - completely standalone
        const popupElement = document.createElement('div');
        popupElement.id = popupId;
        popupElement.setAttribute('style', `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.75);
            z-index: 99999999;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            box-sizing: border-box;
        `);

        // Create container
        popupElement.innerHTML = `
            <div style="
                background-color: white;
                border-radius: 5px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.5);
                width: 90%;
                max-width: 800px;
                max-height: 90vh;
                overflow-y: auto;
                position: relative;
                padding: 20px;
                box-sizing: border-box;
            ">
                <h2 style="margin-top:0; font-size: 1.5rem; border-bottom: 1px solid #eee; padding-bottom: 10px;">
                    Détails du Lead #${leadId}
                </h2>
                <div id="${detailsId}" style="margin:15px 0;">
                    <div style="text-align:center; padding: 30px 0;">
                        <div style="
                            width: 40px;
                            height: 40px;
                            border: 4px solid #f3f3f3;
                            border-top: 4px solid #3498db;
                            border-radius: 50%;
                            margin: 0 auto 15px auto;
                            animation: leadSpin 1s linear infinite;
                        "></div>
                        <p style="margin-top: 15px; color: #666;">Chargement des détails...</p>
                        <style>
                            @keyframes leadSpin {
                                0% { transform: rotate(0deg); }
                                100% { transform: rotate(360deg); }
                            }
                        </style>
                    </div>
                </div>
                <div style="text-align:right; margin-top:20px; padding-top: 15px; border-top: 1px solid #eee;">
                    <button id="lead-contacted-${leadId}" style="
                        background-color: #007bff;
                        color: white;
                        border: none;
                        padding: 8px 15px;
                        margin-right: 10px;
                        border-radius: 4px;
                        cursor: pointer;
                    ">Marquer comme contacté</button>
                    <button id="lead-close-${leadId}" style="
                        background-color: #6c757d;
                        color: white;
                        border: none;
                        padding: 8px 15px;
                        border-radius: 4px;
                        cursor: pointer;
                    ">Fermer</button>
                </div>
                <button id="lead-x-${leadId}" style="
                    position: absolute;
                    top: 10px;
                    right: 10px;
                    background: none;
                    border: none;
                    font-size: 24px;
                    cursor: pointer;
                    color: #666;
                ">&times;</button>
            </div>
        `;

        // STEP 2: Add to document body
        document.body.appendChild(popupElement);

        // STEP 3: Add event handlers directly
        document.getElementById(`lead-close-${leadId}`).onclick = function () {
            popupElement.remove();
        };

        document.getElementById(`lead-x-${leadId}`).onclick = function () {
            popupElement.remove();
        };

        document.getElementById(`lead-contacted-${leadId}`).onclick = function () {
            const token = localStorage.getItem('access_token');

            fetch('/api/leads/status-update/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token
                },
                body: JSON.stringify({
                    lead_ids: [leadId],
                    status: 'contacted'
                })
            })
                .then(response => {
                    console.log("Status update response:", response.status);
                    if (response.ok) {
                        alert('Lead statut mis à jour avec succès!');
                        popupElement.remove();

                        // Reload the current page of leads to reflect the change
                        loadUserLeads(state.filter, state.pagination.currentPage);
                    } else {
                        throw new Error('Erreur de mise à jour: ' + response.status);
                    }
                })
                .catch(err => {
                    console.error("Error updating lead status:", err);
                    alert('Erreur lors de la mise à jour: ' + err.message);
                });
        };

        // STEP 4: Fetch lead data directly
        console.log("Fetching lead details from API:", leadId);
        const token = localStorage.getItem('access_token');

        fetch(`/api/leads/${leadId}/`, {
            headers: {
                'Authorization': 'Bearer ' + token
            }
        })
            .then(response => {
                console.log("Lead details API response status:", response.status);
                if (!response.ok) {
                    throw new Error(`Erreur ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(lead => {
                console.log("Lead data received:", lead);

                // Get details container
                const detailsElement = document.getElementById(detailsId);
                if (!detailsElement) {
                    console.error("Details container not found:", detailsId);
                    return;
                }

                // Format status for display
                const getStatusStyle = (status) => {
                    switch (status) {
                        case 'contacted': return 'color: #fff; background-color: #007bff; padding: 3px 8px; border-radius: 12px;';
                        case 'interested': return 'color: #fff; background-color: #28a745; padding: 3px 8px; border-radius: 12px;';
                        case 'not_interested': return 'color: #fff; background-color: #dc3545; padding: 3px 8px; border-radius: 12px;';
                        default: return 'color: #fff; background-color: #6c757d; padding: 3px 8px; border-radius: 12px;';
                    }
                };

                // Build HTML content for lead details
                let contentHTML = `
                <table style="width:100%; border-collapse:collapse; margin:15px 0;">
                    <tr style="border-bottom:1px solid #eee;">
                        <th style="text-align:left; padding:8px; width:140px;">Nom</th>
                        <td style="padding:8px;">${lead.name || '<span style="color:#999">Non renseigné</span>'}</td>
                    </tr>
                    <tr style="border-bottom:1px solid #eee;">
                        <th style="text-align:left; padding:8px;">Entreprise</th>
                        <td style="padding:8px;">${lead.company || '<span style="color:#999">Non renseigné</span>'}</td>
                    </tr>
                    <tr style="border-bottom:1px solid #eee;">
                        <th style="text-align:left; padding:8px;">Email</th>
                        <td style="padding:8px;">${lead.email || '<span style="color:#999">Non renseigné</span>'}</td>
                    </tr>
                    <tr style="border-bottom:1px solid #eee;">
                        <th style="text-align:left; padding:8px;">Téléphone</th>
                        <td style="padding:8px;">${lead.phone || '<span style="color:#999">Non renseigné</span>'}</td>
                    </tr>
                    <tr style="border-bottom:1px solid #eee;">
                        <th style="text-align:left; padding:8px;">Position</th>
                        <td style="padding:8px;">${lead.position || '<span style="color:#999">Non renseigné</span>'}</td>
                    </tr>
                    <tr style="border-bottom:1px solid #eee;">
                        <th style="text-align:left; padding:8px;">Statut</th>
                        <td style="padding:8px;"><span style="${getStatusStyle(lead.status)}">${lead.status_display || lead.status || 'Non défini'}</span></td>
                    </tr>
                    <tr style="border-bottom:1px solid #eee;">
                        <th style="text-align:left; padding:8px;">Source</th>
                        <td style="padding:8px;">${lead.source || '<span style="color:#999">Non renseigné</span>'}</td>
                    </tr>
                    <tr style="border-bottom:1px solid #eee;">
                        <th style="text-align:left; padding:8px;">URL Source</th>
                        <td style="padding:8px;">${lead.source_url ?
                        `<a href="${lead.source_url}" target="_blank" style="color:#007bff; text-decoration:none;">${lead.source_url}</a>` :
                        '<span style="color:#999">Non renseigné</span>'}</td>
                    </tr>
                    <tr style="border-bottom:1px solid #eee;">
                        <th style="text-align:left; padding:8px;">Créé le</th>
                        <td style="padding:8px;">${new Date(lead.created_at).toLocaleString('fr-FR')}</td>
                    </tr>
                </table>
            `;

                // Add additional data if available
                if (lead.data && typeof lead.data === 'object' && Object.keys(lead.data).length > 0) {
                    contentHTML += `
                    <h3 style="font-size: 18px; margin: 20px 0 10px 0; padding-bottom: 5px; border-bottom: 1px solid #eee;">
                        Données additionnelles
                    </h3>
                    <table style="width:100%; border-collapse:collapse; margin:10px 0;">
                `;

                    for (const [key, value] of Object.entries(lead.data)) {
                        if (value && value !== 'None' && value !== 'null') {
                            const displayKey = key.replace(/_/g, ' ').replace(/^./, m => m.toUpperCase());
                            const isUrl = typeof value === 'string' && (value.startsWith('http://') || value.startsWith('https://'));
                            const displayValue = isUrl
                                ? `<a href="${value}" target="_blank" style="color:#007bff; text-decoration:none;">${value}</a>`
                                : value;

                            contentHTML += `
                            <tr style="border-bottom:1px solid #eee;">
                                <th style="text-align:left; padding:8px; width:140px;">${displayKey}</th>
                                <td style="padding:8px;">${displayValue}</td>
                            </tr>
                        `;
                        }
                    }

                    contentHTML += `</table>`;
                }

                // Update container with content
                detailsElement.innerHTML = contentHTML;
            })
            .catch(error => {
                console.error("Error fetching lead details:", error);

                const detailsElement = document.getElementById(detailsId);
                if (detailsElement) {
                    detailsElement.innerHTML = `
                    <div style="
                        color: #721c24;
                        background-color: #f8d7da;
                        padding: 15px;
                        margin: 10px 0;
                        border: 1px solid #f5c6cb;
                        border-radius: 4px;
                    ">
                        <h3 style="margin-top:0; font-size: 18px;">Erreur</h3>
                        <p>Impossible de charger les détails du lead: ${error.message}</p>
                    </div>
                `;
                }
            });
    };

    /**
     * Mettre à jour les contrôles de pagination
     */
    const updatePaginationControls = () => {
        const prevBtn = document.querySelector(config.elements.prevPageBtn);
        const nextBtn = document.querySelector(config.elements.nextPageBtn);
        const paginationInfo = document.querySelector(config.elements.paginationInfo);

        if (prevBtn) {
            prevBtn.disabled = state.pagination.currentPage <= 1;
        }

        if (nextBtn) {
            nextBtn.disabled = state.pagination.currentPage >= state.pagination.totalPages;
        }

        if (paginationInfo) {
            paginationInfo.textContent = `Page ${state.pagination.currentPage} sur ${state.pagination.totalPages}`;
        }
    };

    /**
     * Créer la fenêtre modale pour les détails de lead si elle n'existe pas
     */
    const createLeadDetailModal = () => {
        console.log('Creating lead detail modal');

        // Check if modal already exists
        const existingModal = document.getElementById('leadDetailModal');
        if (existingModal) {
            console.log('Modal already exists, skipping creation');
            return;
        }

        console.log('Modal does not exist, creating it now');

        // Create the modal structure
        const modalHtml = `
            <div class="modal fade" id="leadDetailModal" tabindex="-1" aria-labelledby="leadDetailModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="leadDetailModalLabel">Détails du lead</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div id="leadDetailContent" class="p-2">
                                <div class="text-center py-4">
                                    <div class="spinner-border text-primary" role="status">
                                        <span class="visually-hidden">Chargement...</span>
                                    </div>
                                    <p class="mt-2">Chargement des détails...</p>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fermer</button>
                            <div class="btn-group">
                                <button type="button" class="btn btn-outline-primary" id="mark-contacted-modal-btn">
                                    <i class="fas fa-check me-1"></i> Marquer comme contacté
                                </button>
                                <button type="button" class="btn btn-outline-success" id="mark-interested-modal-btn">
                                    <i class="fas fa-thumbs-up me-1"></i> Marquer comme intéressé
                                </button>
                                <button type="button" class="btn btn-outline-danger" id="mark-not-interested-modal-btn">
                                    <i class="fas fa-thumbs-down me-1"></i> Marquer comme pas intéressé
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Create a temporary div to hold our modal HTML
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = modalHtml.trim();

        // Get the modal element from the temporary div
        const modalElement = tempDiv.firstChild;

        // Append to body
        console.log('Appending modal to document body');
        document.body.appendChild(modalElement);

        console.log('Modal created successfully, element ID:', modalElement.id);
    };

    /**
     * Check if Bootstrap is properly loaded and available
     */
    const checkBootstrapAvailability = () => {
        console.log('Checking Bootstrap availability...');

        // Check if bootstrap is defined
        if (typeof bootstrap === 'undefined') {
            console.error('Bootstrap is not defined! Modal functionality may not work correctly.');
            return false;
        }

        // Check if Modal is available
        if (typeof bootstrap.Modal === 'undefined') {
            console.error('Bootstrap.Modal is not defined! Modal functionality may not work correctly.');
            return false;
        }

        console.log('Bootstrap is properly loaded and Modal is available');
        return true;
    };

    // API publique
    return {
        init,
        createProfileWelcomePopup
    };
})();

// Si nous sommes sur la page d'accueil du dashboard (vue d'ensemble), afficher le popup
document.addEventListener('DOMContentLoaded', function () {
    // Vérifier si nous sommes sur la page dashboard
    if (window.location.pathname.includes('/dashboard')) {
        // Attendre que les données soient chargées (attente courte)
        setTimeout(function () {
            // Vérifier si l'API publique existe
            if (typeof WizzyIndustryEnrichment !== 'undefined' &&
                typeof WizzyIndustryEnrichment.createProfileWelcomePopup === 'function') {

                // Vérifier si on doit montrer le popup
                const hasNoProfile = !localStorage.getItem('wizzy_user_has_profile');
                const shouldShow = localStorage.getItem('wizzy_profile_popup_shown') !== 'true';

                if (hasNoProfile || shouldShow) {
                    WizzyIndustryEnrichment.createProfileWelcomePopup();
                }
            }
        }, 1000);
    }
}); 