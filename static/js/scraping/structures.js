/**
 * Wizzy Scraping Structures Module
 * Handles management of scraping structures detected by AI
 */

const WizzyScrapingStructures = {
    // Keep track of structures
    structures: [],

    // Initialize the module
    init: function () {
        console.log('Initializing scraping structures module');

        // Check authentication
        if (!WizzyUtils.isAuthenticated()) {
            return;
        }

        // Add custom CSS for structure cards
        this.addCustomCSS();

        // Load structures from the API
        this.loadStructures();

        // Set up event listeners for structure actions
        this.setupEventListeners();
    },

    // Add custom CSS for structure editing
    addCustomCSS: function () {
        const styleId = 'wizzy-structure-styles';

        // Only add if it doesn't already exist
        if (!document.getElementById(styleId)) {
            const style = document.createElement('style');
            style.id = styleId;
            style.innerHTML = `
                .lead-target-display {
                    display: flex;
                    align-items: center;
                }
                .lead-target-display .btn-link {
                    color: #6c757d;
                    font-size: 0.8rem;
                    padding: 0;
                    opacity: 0.5;
                    transition: opacity 0.2s;
                }
                .lead-target-display:hover .btn-link {
                    opacity: 1;
                }
                .lead-target-edit .input-group {
                    width: 140px;
                }
                .lead-target-edit .form-control {
                    padding: 0.25rem 0.5rem;
                    font-size: 0.875rem;
                }
                .lead-target-edit .btn {
                    padding: 0.25rem 0.5rem;
                    font-size: 0.875rem;
                }
                
                /* Modal fallback styles */
                .modal-open {
                    overflow: hidden;
                }
                .modal-backdrop {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100vw;
                    height: 100vh;
                    background-color: rgba(0, 0, 0, 0.5);
                    z-index: 1040;
                }
                .modal.show {
                    display: block;
                    z-index: 1050;
                }
            `;
            document.head.appendChild(style);
        }
    },

    // Load structures from the API
    loadStructures: async function () {
        try {
            // Show loading state
            const structuresContainer = document.getElementById('scrapingStructures');
            if (structuresContainer) {
                structuresContainer.innerHTML = `
                    <div class="text-center py-5">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Chargement...</span>
                        </div>
                        <p class="mt-2">Chargement des structures...</p>
                    </div>
                `;
            }

            // Fetch structures
            const response = await WizzyUtils.apiRequest('/api/scraping/structures/');

            if (response.ok) {
                const data = await response.json();
                this.structures = data.structures || [];
                this.renderStructures();
            } else {
                console.error('Failed to load structures');
                WizzyUtils.showAlert('Erreur lors du chargement des structures', 'danger');

                // Use placeholder data for development
                this.loadPlaceholderStructures();
            }
        } catch (error) {
            console.error('Error loading structures:', error);
            WizzyUtils.showAlert('Erreur lors du chargement des structures', 'danger');

            // Use placeholder data for development
            this.loadPlaceholderStructures();
        }
    },

    // Load placeholder structure data for development
    loadPlaceholderStructures: function () {
        // Create placeholder structures
        this.structures = [
            {
                id: 1,
                name: "Mairies Sportives",
                entity_type: "mairie",
                is_active: true,
                created_at: "2023-03-20T10:15:00Z",
                scraping_strategy: "web_scraping",
                leads_target_per_day: 15,
                daily_leads_usage: 8,
                structure: {
                    mairie: {
                        region: "Île-de-France",
                        departement: "Paris",
                        code_postal: "75000",
                        infrastructure_sportive: {
                            piscine: true,
                            gymnase: true,
                            stade: true
                        }
                    }
                }
            },
            {
                id: 2,
                name: "Entreprises Tech Paris",
                entity_type: "entreprise",
                is_active: true,
                created_at: "2023-03-22T14:30:00Z",
                scraping_strategy: "linkedin_scraping",
                leads_target_per_day: 25,
                daily_leads_usage: 20,
                structure: {
                    company: {
                        industry: "Technologie",
                        size: "10-50 employés",
                        location: "Paris",
                        technologies: ["React", "Node.js", "Python"]
                    }
                }
            },
            {
                id: 3,
                name: "Agences Immobilières Lyon",
                entity_type: "b2b_lead",
                is_active: false,
                created_at: "2023-03-18T09:45:00Z",
                scraping_strategy: "serp_scraping",
                leads_target_per_day: 10,
                daily_leads_usage: 3,
                structure: {
                    industry: "Immobilier",
                    location: "Lyon",
                    company_size: "PME"
                }
            }
        ];

        // Render the structures
        this.renderStructures();
    },

    // Render structures in the UI
    renderStructures: function () {
        const structuresContainer = document.getElementById('scrapingStructures');
        if (!structuresContainer) return;

        if (this.structures.length === 0) {
            structuresContainer.innerHTML = `
                <div class="text-center py-5">
                    <div class="empty-state">
                        <i class="fas fa-search fa-4x text-muted mb-3"></i>
                        <h4>Aucune structure de scraping</h4>
                        <p class="text-muted">
                            Utilisez le chat IA pour créer des structures de scraping
                            basées sur vos besoins.
                        </p>
                        <button class="btn btn-primary mt-3" onclick="WizzyChat.toggle()">
                            <i class="fas fa-comment"></i> Ouvrir le chat
                        </button>
                    </div>
                </div>
            `;
            return;
        }

        // Group structures by entity type
        const structuresByType = {};
        this.structures.forEach(structure => {
            if (!structuresByType[structure.entity_type]) {
                structuresByType[structure.entity_type] = [];
            }
            structuresByType[structure.entity_type].push(structure);
        });

        // Create HTML for each group
        let html = '';

        Object.keys(structuresByType).forEach(entityType => {
            html += `
                <div class="structure-group mb-4">
                    <h4 class="mb-3">${WizzyUtils.getEntityTypeLabel(entityType)}</h4>
                    <div class="row">
            `;

            // Add cards for each structure
            structuresByType[entityType].forEach(structure => {
                html += this.renderStructureCard(structure);
            });

            html += `
                    </div>
                </div>
            `;
        });

        structuresContainer.innerHTML = html;
    },

    // Render a single structure card
    renderStructureCard: function (structure) {
        // Format dates
        const createdDate = WizzyUtils.formatDate(structure.created_at);

        // Parse the structure JSON data
        let structureFormatted = '';
        try {
            if (typeof structure.structure === 'string') {
                structure.structure = JSON.parse(structure.structure);
            }

            // Format structure data for display
            structureFormatted = this.formatStructureDetails(structure.structure, structure.entity_type);
        } catch (e) {
            console.error('Error parsing structure:', e);
            structureFormatted = '<p class="text-danger">Error parsing structure data</p>';
        }

        // Usage statistics (daily leads counter)
        const dailyLeads = structure.daily_leads_usage || 0;
        const targetLeads = structure.leads_target_per_day || 10;
        const usagePercent = Math.min(Math.round((dailyLeads / targetLeads) * 100), 100);
        const usageColor = usagePercent > 80 ? 'danger' : (usagePercent > 60 ? 'warning' : 'success');

        return `
            <div class="col-md-6 col-lg-4 mb-4">
                <div class="card h-100 ${structure.is_active ? '' : 'bg-light'}">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5 class="card-title mb-0 text-truncate" title="${structure.name}">
                            ${structure.name}
                        </h5>
                        <div class="structure-badge">
                            ${structure.is_active
                ? '<span class="badge bg-success">Actif</span>'
                : '<span class="badge bg-secondary">Inactif</span>'}
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="structure-info mb-3">
                            <div class="mb-2">
                                <i class="fas fa-calendar-alt text-muted me-2"></i>
                                <span>Créé le ${createdDate}</span>
                            </div>
                            <div class="mb-2">
                                <i class="fas fa-code-branch text-muted me-2"></i>
                                <span>Stratégie: ${structure.scraping_strategy}</span>
                            </div>
                            
                            <!-- Daily Leads Target and Allocation - Enhanced with inline editing -->
                            <div class="mb-2">
                                <div class="d-flex justify-content-between align-items-center">
                                    <div>
                                        <i class="fas fa-chart-line text-muted me-2"></i>
                                        <span>Objectif:</span>
                                    </div>
                                    <div class="lead-target-display">
                                        <span>${targetLeads} leads/jour</span>
                                        <button class="btn btn-sm btn-link p-0 ms-2 edit-target-btn" data-structure-id="${structure.id}">
                                            <i class="fas fa-edit"></i>
                                        </button>
                                    </div>
                                    <div class="lead-target-edit d-none">
                                        <div class="input-group input-group-sm">
                                            <input type="number" class="form-control form-control-sm lead-target-input" 
                                                   value="${targetLeads}" min="1" max="1000" style="width: 70px;">
                                            <button class="btn btn-sm btn-primary save-target-btn" data-structure-id="${structure.id}">
                                                <i class="fas fa-save"></i>
                                            </button>
                                            <button class="btn btn-sm btn-secondary cancel-edit-btn">
                                                <i class="fas fa-times"></i>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Daily Leads Usage Counter -->
                            <div class="mt-3">
                                <label class="form-label d-flex justify-content-between">
                                    <span>Utilisation quotidienne</span>
                                    <span>${dailyLeads}/${targetLeads} leads</span>
                                </label>
                                <div class="progress" style="height: 8px;">
                                    <div class="progress-bar bg-${usageColor}" role="progressbar" 
                                         style="width: ${usagePercent}%" 
                                         aria-valuenow="${dailyLeads}" aria-valuemin="0" 
                                         aria-valuemax="${targetLeads}"></div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="structure-details">
                            <h6>Structure:</h6>
                            <div class="structure-data">
                                ${structureFormatted}
                            </div>
                        </div>
                    </div>
                    <div class="card-footer">
                        <div class="d-flex justify-content-between">
                            <button class="btn btn-sm btn-outline-primary" 
                                    onclick="WizzyScrapingStructures.showStructureDetails(${structure.id})">
                                <i class="fas fa-eye"></i> Détails
                            </button>
                            
                            <div class="btn-group">
                                <button class="btn btn-sm btn-outline-secondary" 
                                        onclick="WizzyScrapingStructures.toggleStructureStatus(${structure.id}, ${structure.is_active})">
                                    ${structure.is_active
                ? '<i class="fas fa-pause"></i> Désactiver'
                : '<i class="fas fa-play"></i> Activer'}
                                </button>
                                <button class="btn btn-sm btn-outline-success" 
                                        onclick="window.launchScrapingTask(${structure.id})">
                                    <i class="fas fa-rocket"></i> Lancer
                                </button>
                                <button class="btn btn-sm btn-outline-danger" 
                                        onclick="WizzyScrapingStructures.deleteStructure(${structure.id})">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    // Format structure details for display
    formatStructureDetails: function (structure, entityType) {
        if (!structure) return '<p class="text-muted">Pas de détails disponibles</p>';

        let html = '<ul class="list-unstyled">';

        // Customize display based on entity type
        if (entityType === 'mairie') {
            const mairie = structure.mairie || structure;

            if (mairie.region) html += `<li><strong>Région:</strong> ${mairie.region}</li>`;
            if (mairie.departement) html += `<li><strong>Département:</strong> ${mairie.departement}</li>`;
            if (mairie.code_postal) html += `<li><strong>Code postal:</strong> ${mairie.code_postal}</li>`;

            if (mairie.infrastructure_sportive) {
                html += '<li><strong>Infrastructures sportives:</strong> ';
                if (typeof mairie.infrastructure_sportive === 'object') {
                    html += '<ul>';
                    for (const [key, value] of Object.entries(mairie.infrastructure_sportive)) {
                        if (value === true) {
                            html += `<li>${key.replace(/_/g, ' ')}</li>`;
                        }
                    }
                    html += '</ul>';
                } else {
                    html += mairie.infrastructure_sportive;
                }
                html += '</li>';
            }
        } else if (entityType === 'entreprise' || entityType === 'b2b_lead') {
            const company = structure.company || structure.entreprise || structure;

            if (company.industry) html += `<li><strong>Secteur:</strong> ${company.industry}</li>`;
            if (company.size) html += `<li><strong>Taille:</strong> ${company.size}</li>`;
            if (company.revenue) html += `<li><strong>Chiffre d'affaires:</strong> ${company.revenue}</li>`;
            if (company.location) html += `<li><strong>Localisation:</strong> ${company.location}</li>`;
            if (company.technologies) {
                html += `<li><strong>Technologies:</strong> ${Array.isArray(company.technologies) ? company.technologies.join(', ') : company.technologies}</li>`;
            }
        } else {
            // Generic display for custom structures
            for (const [key, value] of Object.entries(structure)) {
                if (typeof value !== 'object') {
                    html += `<li><strong>${key}:</strong> ${value}</li>`;
                }
            }
        }

        html += '</ul>';

        // Add a "View all" option if the structure is complex
        if (Object.keys(structure).length > 5) {
            html += '<div class="text-center mt-2"><a href="#" class="small">Voir tous les champs</a></div>';
        }

        return html;
    },

    // Create a Bootstrap modal safely
    createModal: function (id, title, content, footerButtons) {
        // Create a unique ID for the modal
        const modalId = id || `modal-${Date.now()}`;

        // Check if the modal already exists
        let modalElement = document.getElementById(modalId);

        // If it exists, return it
        if (modalElement) {
            return modalElement;
        }

        // Create the modal HTML
        const modalHTML = `
            <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="${modalId}Label" aria-hidden="true">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="${modalId}Label">${title || 'Modal'}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            ${content || ''}
                        </div>
                        <div class="modal-footer">
                            ${footerButtons || '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fermer</button>'}
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Create the element
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = modalHTML.trim();
        modalElement = tempDiv.firstChild;

        // Append to the document body
        document.body.appendChild(modalElement);

        // Return the created modal element
        return modalElement;
    },

    // Show structure details in a modal
    showStructureDetails: function (structureId) {
        // Find the structure
        const structure = this.structures.find(s => s.id === structureId);
        if (!structure) {
            console.error('Structure not found');
            return;
        }

        // Format structure data
        const formattedDate = WizzyUtils.formatDate(structure.created_at);
        const strategyLabel = this.getStrategyLabel(structure.scraping_strategy);

        // Format structure JSON as a pretty-printed string
        let structureJson = '';
        if (typeof structure.structure === 'string') {
            try {
                structureJson = JSON.stringify(JSON.parse(structure.structure), null, 2);
            } catch (e) {
                structureJson = structure.structure;
            }
        } else {
            structureJson = JSON.stringify(structure.structure, null, 2);
        }

        // Create modal content
        const content = `
            <div class="structure-detail-info mb-4">
                <div class="row">
                    <div class="col-md-6">
                        <p><strong>Type:</strong> ${WizzyUtils.getEntityTypeLabel(structure.entity_type)}</p>
                        <p><strong>Créé le:</strong> ${formattedDate}</p>
                        <p><strong>Status:</strong> 
                            <span class="badge ${structure.is_active ? 'bg-success' : 'bg-secondary'}">
                                ${structure.is_active ? 'Actif' : 'Inactif'}
                            </span>
                        </p>
                    </div>
                    <div class="col-md-6">
                        <p><strong>Stratégie:</strong> ${strategyLabel}</p>
                        <p><strong>Objectif:</strong> ${structure.leads_target_per_day} leads/jour</p>
                        <p>
                            <button class="btn btn-sm btn-outline-primary mb-2" id="editTargetBtn">
                                <i class="fas fa-edit"></i> Modifier l'objectif
                            </button>
                        </p>
                    </div>
                </div>
            </div>
            
            <h5>Structure de données</h5>
            <div class="structure-json mb-3">
                <pre class="p-3 rounded"><code>${structureJson}</code></pre>
            </div>
            
            <div id="structureLeadsTarget" class="mt-4 d-none">
                <h5>Modifier l'objectif de leads</h5>
                <div class="input-group mb-3">
                    <input type="number" class="form-control" id="leadsTargetInput" min="1" max="1000" 
                           value="${structure.leads_target_per_day}">
                    <button class="btn btn-primary" type="button" id="saveTargetBtn">Enregistrer</button>
                </div>
            </div>
        `;

        // Create footer buttons
        const footerButtons = `
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fermer</button>
            <button type="button" class="btn btn-primary" id="structureCreateJobBtn">
                <i class="fas fa-rocket"></i> Créer une tâche
            </button>
        `;

        // Create modal
        const modalElement = this.createModal('structureDetailModal', structure.name, content, footerButtons);

        // Set up event listeners
        const editTargetBtn = modalElement.querySelector('#editTargetBtn');
        if (editTargetBtn) {
            editTargetBtn.addEventListener('click', () => {
                const targetSection = modalElement.querySelector('#structureLeadsTarget');
                if (targetSection) {
                    targetSection.classList.toggle('d-none');
                    const targetInput = modalElement.querySelector('#leadsTargetInput');
                    if (targetInput) targetInput.focus();
                }
            });
        }

        const saveTargetBtn = modalElement.querySelector('#saveTargetBtn');
        if (saveTargetBtn) {
            saveTargetBtn.addEventListener('click', () => {
                const targetInput = modalElement.querySelector('#leadsTargetInput');
                if (targetInput) {
                    const leadsTarget = parseInt(targetInput.value);
                    this.updateLeadsTarget(structure.id, leadsTarget);

                    const targetSection = modalElement.querySelector('#structureLeadsTarget');
                    if (targetSection) targetSection.classList.add('d-none');
                }
            });
        }

        const createJobBtn = modalElement.querySelector('#structureCreateJobBtn');
        if (createJobBtn) {
            createJobBtn.addEventListener('click', () => {
                // Close the modal first
                const bsModal = bootstrap.Modal.getInstance(modalElement);
                if (bsModal) bsModal.hide();

                // Launch scraping task
                if (typeof window.launchScrapingTask === 'function') {
                    window.launchScrapingTask(structure.id);
                } else {
                    console.error('launchScrapingTask function not found');
                    // Fallback to old method
                    if (typeof WizzyScrapingJobs !== 'undefined' && typeof WizzyScrapingJobs.createNewJob === 'function') {
                        WizzyScrapingJobs.createNewJob(structure.id);
                    } else {
                        alert('Erreur: Module de tâches non disponible');
                    }
                }
            });
        }

        // Show the modal using Bootstrap
        try {
            if (typeof bootstrap !== 'undefined') {
                const bsModal = new bootstrap.Modal(modalElement);
                bsModal.show();
            } else {
                // Fallback if bootstrap is not accessible
                modalElement.classList.add('show');
                modalElement.style.display = 'block';
                document.body.classList.add('modal-open');

                const backdrop = document.createElement('div');
                backdrop.className = 'modal-backdrop fade show';
                document.body.appendChild(backdrop);

                // Add click handler to close button
                const closeBtn = modalElement.querySelector('[data-bs-dismiss="modal"]');
                if (closeBtn) {
                    closeBtn.addEventListener('click', () => {
                        modalElement.classList.remove('show');
                        modalElement.style.display = 'none';
                        document.body.classList.remove('modal-open');
                        backdrop.remove();
                    });
                }
            }
        } catch (error) {
            console.error('Error showing modal:', error);
            WizzyUtils.showAlert('Erreur lors de l\'affichage des détails', 'danger');
        }
    },

    // Get a human-readable label for a scraping strategy
    getStrategyLabel: function (strategy) {
        const labels = {
            'custom_scraping': 'Scraping personnalisé',
            'linkedin_scraping': 'Scraping LinkedIn',
            'web_scraping': 'Scraping Web',
            'serp_scraping': 'Scraping des résultats de recherche'
        };

        return labels[strategy] || strategy;
    },

    // Toggle the active status of a structure
    toggleStructureStatus: async function (structureId, currentStatus) {
        try {
            const response = await WizzyUtils.apiRequest(`/api/scraping/structures/${structureId}/`, {
                method: 'PUT',
                body: JSON.stringify({
                    action: 'toggle_status'
                })
            });

            if (response.ok) {
                const data = await response.json();

                if (data.success) {
                    // Update the structure in our local copy
                    const structureIndex = this.structures.findIndex(s => s.id === structureId);
                    if (structureIndex !== -1) {
                        this.structures[structureIndex].is_active = !currentStatus;
                        this.renderStructures();
                    }

                    // Show success message
                    WizzyUtils.showAlert(data.message, 'success');
                } else {
                    WizzyUtils.showAlert(data.error || 'Une erreur est survenue', 'danger');
                }
            } else {
                WizzyUtils.showAlert('Erreur lors de la mise à jour du statut', 'danger');
            }
        } catch (error) {
            console.error('Error toggling structure status:', error);
            WizzyUtils.showAlert('Erreur lors de la mise à jour du statut', 'danger');
        }
    },

    // Update leads target for a structure
    updateLeadsTarget: async function (structureId, leadsTarget) {
        try {
            if (!leadsTarget || leadsTarget < 1) {
                WizzyUtils.showAlert('Veuillez entrer un objectif valide (1 ou plus)', 'warning');
                return;
            }

            const response = await WizzyUtils.apiRequest(`/api/scraping/structures/${structureId}/`, {
                method: 'PUT',
                body: JSON.stringify({
                    action: 'set_target',
                    leads_target_per_day: leadsTarget
                })
            });

            if (response.ok) {
                const data = await response.json();

                if (data.success) {
                    // Update the structure in our local copy
                    const structureIndex = this.structures.findIndex(s => s.id === structureId);
                    if (structureIndex !== -1) {
                        const structure = this.structures[structureIndex];
                        const oldTarget = structure.leads_target_per_day;

                        // Update the structure object
                        structure.leads_target_per_day = leadsTarget;

                        // Update the UI elements directly for the specific structure
                        const cards = document.querySelectorAll('.card');
                        for (const card of cards) {
                            const editBtn = card.querySelector(`.edit-target-btn[data-structure-id="${structureId}"]`);
                            if (editBtn) {
                                // Found the card that contains this structure
                                // Update the display text
                                const displayElem = card.querySelector('.lead-target-display span');
                                if (displayElem) {
                                    displayElem.textContent = `${leadsTarget} leads/jour`;
                                }

                                // Update the input value
                                const inputElem = card.querySelector('.lead-target-input');
                                if (inputElem) {
                                    inputElem.value = leadsTarget;
                                }

                                // Update the progress bar
                                const progressBar = card.querySelector('.progress-bar');
                                const usageLabel = card.querySelector('.form-label span:last-child');
                                const dailyLeads = structure.daily_leads_usage || 0;

                                if (progressBar && usageLabel) {
                                    const usagePercent = Math.min(Math.round((dailyLeads / leadsTarget) * 100), 100);
                                    const usageColor = usagePercent > 80 ? 'danger' : (usagePercent > 60 ? 'warning' : 'success');

                                    // Update the classes for the progress bar
                                    progressBar.classList.remove('bg-danger', 'bg-warning', 'bg-success');
                                    progressBar.classList.add(`bg-${usageColor}`);

                                    // Update the width
                                    progressBar.style.width = `${usagePercent}%`;

                                    // Update the lead count label
                                    usageLabel.textContent = `${dailyLeads}/${leadsTarget} leads`;
                                }

                                break;
                            }
                        }
                    }

                    // Show success message
                    WizzyUtils.showAlert('Objectif de leads mis à jour', 'success');
                } else {
                    WizzyUtils.showAlert(data.error || 'Une erreur est survenue', 'danger');
                }
            } else {
                WizzyUtils.showAlert('Erreur lors de la mise à jour de l\'objectif', 'danger');

                // For development only - simulate success when API is not available
                const structureIndex = this.structures.findIndex(s => s.id === parseInt(structureId));
                if (structureIndex !== -1) {
                    // Apply the update to our local data
                    this.structures[structureIndex].leads_target_per_day = leadsTarget;

                    // Update the UI to reflect the change
                    const cards = document.querySelectorAll('.card');
                    for (const card of cards) {
                        const editBtn = card.querySelector(`.edit-target-btn[data-structure-id="${structureId}"]`);
                        if (editBtn) {
                            // Found the card
                            const displayElem = card.querySelector('.lead-target-display span');
                            if (displayElem) {
                                displayElem.textContent = `${leadsTarget} leads/jour`;
                            }

                            // Update other elements
                            const inputElem = card.querySelector('.lead-target-input');
                            if (inputElem) {
                                inputElem.value = leadsTarget;
                            }

                            // Update the progress bar
                            const progressBar = card.querySelector('.progress-bar');
                            const usageLabel = card.querySelector('.form-label span:last-child');
                            const dailyLeads = this.structures[structureIndex].daily_leads_usage || 0;

                            if (progressBar && usageLabel) {
                                const usagePercent = Math.min(Math.round((dailyLeads / leadsTarget) * 100), 100);
                                const usageColor = usagePercent > 80 ? 'danger' : (usagePercent > 60 ? 'warning' : 'success');

                                progressBar.classList.remove('bg-danger', 'bg-warning', 'bg-success');
                                progressBar.classList.add(`bg-${usageColor}`);
                                progressBar.style.width = `${usagePercent}%`;
                                usageLabel.textContent = `${dailyLeads}/${leadsTarget} leads`;
                            }

                            break;
                        }
                    }

                    // Show a success message
                    WizzyUtils.showAlert('Objectif de leads mis à jour (mode développement)', 'success');
                }
            }
        } catch (error) {
            console.error('Error updating leads target:', error);
            WizzyUtils.showAlert('Erreur lors de la mise à jour de l\'objectif', 'danger');
        }
    },

    // Delete a structure
    deleteStructure: async function (structureId) {
        // Confirm before deleting
        if (!confirm('Êtes-vous sûr de vouloir supprimer cette structure ?')) {
            return;
        }

        try {
            const response = await WizzyUtils.apiRequest(`/api/scraping/structures/${structureId}/`, {
                method: 'DELETE'
            });

            if (response.ok) {
                const data = await response.json();

                if (data.success) {
                    // Remove the structure from our local copy
                    this.structures = this.structures.filter(s => s.id !== structureId);
                    this.renderStructures();

                    // Show success message
                    WizzyUtils.showAlert(data.message, 'success');
                } else {
                    WizzyUtils.showAlert(data.error || 'Une erreur est survenue', 'danger');
                }
            } else {
                WizzyUtils.showAlert('Erreur lors de la suppression de la structure', 'danger');
            }
        } catch (error) {
            console.error('Error deleting structure:', error);
            WizzyUtils.showAlert('Erreur lors de la suppression de la structure', 'danger');
        }
    },

    // Setup event listeners
    setupEventListeners: function () {
        // Event delegation for structure card interactions
        document.addEventListener('click', (event) => {
            // Handle edit target button clicks
            if (event.target.closest('.edit-target-btn')) {
                const button = event.target.closest('.edit-target-btn');
                const structureCard = button.closest('.card');

                if (structureCard) {
                    const displayElement = structureCard.querySelector('.lead-target-display');
                    const editElement = structureCard.querySelector('.lead-target-edit');

                    if (displayElement && editElement) {
                        displayElement.classList.add('d-none');
                        editElement.classList.remove('d-none');

                        // Focus the input
                        const input = editElement.querySelector('.lead-target-input');
                        if (input) input.focus();
                    }
                }
            }

            // Handle save target button clicks
            else if (event.target.closest('.save-target-btn')) {
                const button = event.target.closest('.save-target-btn');
                const structureId = button.dataset.structureId;
                const structureCard = button.closest('.card');

                if (structureCard) {
                    const input = structureCard.querySelector('.lead-target-input');
                    const displayElement = structureCard.querySelector('.lead-target-display');
                    const editElement = structureCard.querySelector('.lead-target-edit');

                    if (input && displayElement && editElement) {
                        const leadsTarget = parseInt(input.value);

                        // Update the target
                        this.updateLeadsTarget(structureId, leadsTarget);

                        // Hide edit form
                        displayElement.classList.remove('d-none');
                        editElement.classList.add('d-none');
                    }
                }
            }

            // Handle cancel edit button clicks
            else if (event.target.closest('.cancel-edit-btn')) {
                const button = event.target.closest('.cancel-edit-btn');
                const structureCard = button.closest('.card');

                if (structureCard) {
                    const displayElement = structureCard.querySelector('.lead-target-display');
                    const editElement = structureCard.querySelector('.lead-target-edit');

                    if (displayElement && editElement) {
                        displayElement.classList.remove('d-none');
                        editElement.classList.add('d-none');
                    }
                }
            }
        });
    }
};

// Variable to hold refresh interval
let structuresRefreshInterval = null;

// Initialize the page
document.addEventListener('DOMContentLoaded', function () {
    // Load scraping structures
    loadScrapingStructures();

    // Setup refresh interval
    startStructuresAutoRefresh();

    // Clean up on page unload
    window.addEventListener('beforeunload', function () {
        stopStructuresAutoRefresh();
    });
});

// Start auto-refresh for structures data
function startStructuresAutoRefresh() {
    // Stop any existing refresh
    stopStructuresAutoRefresh();

    // Set new interval to refresh every 45 seconds
    structuresRefreshInterval = setInterval(() => {
        console.log('Auto-refreshing structures data');
        loadScrapingStructures();
    }, 45000);
}

// Stop auto-refresh
function stopStructuresAutoRefresh() {
    if (structuresRefreshInterval) {
        clearInterval(structuresRefreshInterval);
        structuresRefreshInterval = null;
    }
}

function loadScrapingStructures() {
    const container = document.getElementById('scrapingStructures');
    if (!container) return;

    // Show loading indicator
    container.innerHTML = `
        <div class="text-center py-4">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Chargement...</span>
            </div>
            <p class="mt-2">Chargement des structures...</p>
        </div>
    `;

    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    fetch(`/api/structures/?_=${timestamp}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load scraping structures');
            }
            return response.json();
        })
        .then(data => {
            renderStructures(data);
        })
        .catch(error => {
            console.error('Error loading structures:', error);
            container.innerHTML = `
                <div class="alert alert-danger">
                    Failed to load scraping structures. Please try again later.
                </div>
            `;
        });
}

function renderStructures(data) {
    const structuresContainer = document.getElementById('scrapingStructures');
    if (!structuresContainer) return;

    if (!data || !data.structures || data.structures.length === 0) {
        structuresContainer.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle me-2"></i>
                No scraping structures found. Start a conversation with Wizzy to detect and create structures.
            </div>
        `;
        return;
    }

    // Get rate limiting information if available
    const rateLimitInfo = data.user_stats || {};
    const leadsUsed = rateLimitInfo.leads_used || 0;
    const leadsQuota = rateLimitInfo.leads_quota || 5;
    const hasRateLimit = rateLimitInfo.has_rate_limit !== false;
    const rateLimitReached = hasRateLimit && leadsUsed >= leadsQuota;
    const rateLimitedLeads = rateLimitInfo.rate_limited_leads || 0;
    const incompleteLeads = rateLimitInfo.incomplete_leads || 0;

    // Build the UI
    let html = '';

    // Show rate limit information
    if (hasRateLimit) {
        const usagePercent = Math.min(Math.round((leadsUsed / leadsQuota) * 100), 100);
        const progressColor = rateLimitReached ? 'danger' : (usagePercent > 80 ? 'warning' : 'primary');

        html += `
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">Quota de leads</h5>
                    <div class="row align-items-center">
                        <div class="col-md-8">
                            <div class="progress mb-2" style="height: 10px;">
                                <div class="progress-bar bg-${progressColor}" role="progressbar" 
                                     style="width: ${usagePercent}%" 
                                     aria-valuenow="${leadsUsed}" aria-valuemin="0" aria-valuemax="${leadsQuota}"></div>
                            </div>
                            <div class="d-flex justify-content-between">
                                <small class="text-muted">Utilisés: ${leadsUsed}</small>
                                <small class="text-muted">Quota total: ${leadsQuota}</small>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="d-flex flex-column">
                                ${rateLimitedLeads > 0 ? `<small class="text-danger mb-1"><i class="fas fa-ban me-1"></i>Leads bloqués: ${rateLimitedLeads}</small>` : ''}
                                ${incompleteLeads > 0 ? `<small class="text-warning mb-1"><i class="fas fa-exclamation-triangle me-1"></i>Leads incomplets: ${incompleteLeads}</small>` : ''}
                                ${rateLimitReached ? `
                                    <div class="mt-2">
                                        <a href="/dashboard/billing/" class="btn btn-sm btn-outline-primary">Augmenter mon quota</a>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // Group structures by type
    const groupedStructures = {};
    data.structures.forEach(structure => {
        if (!groupedStructures[structure.entity_type]) {
            groupedStructures[structure.entity_type] = [];
        }
        groupedStructures[structure.entity_type].push(structure);
    });

    // For each group
    Object.keys(groupedStructures).forEach(type => {
        const structures = groupedStructures[type];
        const typeName = getEntityTypeName(type);

        html += `
            <div class="structure-group mb-4">
                <h4>${typeName} (${structures.length})</h4>
                <div class="row">
        `;

        structures.forEach(structure => {
            // Calculate completion percentage for daily target
            const completionPercentage = structure.daily_current
                ? Math.min(Math.round((structure.daily_current / structure.daily_target) * 100), 100)
                : 0;

            html += `
                <div class="col-md-6 col-lg-4 mb-3">
                    <div class="card structure-card h-100">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">${structure.name}</h5>
                            <span class="badge bg-${getStrategyBadgeColor(structure.scraping_strategy)}">${structure.scraping_strategy}</span>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <label class="form-label">Leads extraits aujourd'hui</label>
                                <div class="progress" style="height: 8px;">
                                    <div class="progress-bar ${completionPercentage > 80 ? 'bg-success' : 'bg-primary'}" 
                                         role="progressbar" style="width: ${completionPercentage}%" 
                                         aria-valuenow="${structure.daily_current}" aria-valuemin="0" aria-valuemax="${structure.daily_target}"></div>
                                </div>
                                <small class="text-muted">${structure.daily_current || 0} sur ${structure.daily_target} (${completionPercentage}%)</small>
                            </div>
                            <div class="structure-props">
                                <p><strong>Objectif:</strong> ${structure.leads_target_per_day} leads/jour</p>
                                <p><strong>Créé le:</strong> ${formatDate(structure.created_at)}</p>
                            </div>
                        </div>
                        <div class="card-footer d-flex justify-content-between">
                            <button class="btn btn-sm btn-outline-primary view-structure" data-id="${structure.id}">
                                <i class="fas fa-eye"></i> Détails
                            </button>
                            <button class="btn btn-sm btn-success start-scraping" data-id="${structure.id}"
                                    ${rateLimitReached ? 'disabled title="Limite de leads atteinte"' : ''}>
                                <i class="fas fa-robot"></i> Lancer
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;
    });

    structuresContainer.innerHTML = html;

    // Add event listeners
    document.querySelectorAll('.view-structure').forEach(button => {
        button.addEventListener('click', function () {
            viewStructureDetails(this.getAttribute('data-id'));
        });
    });

    document.querySelectorAll('.start-scraping').forEach(button => {
        button.addEventListener('click', function () {
            if (!this.disabled) {
                startManualScraping(this.getAttribute('data-id'));
            }
        });
    });
}

function startManualScraping(structureId) {
    // Show confirmation dialog
    if (!confirm('Are you sure you want to start scraping this structure?')) {
        return;
    }

    const button = document.querySelector(`.start-scraping[data-id="${structureId}"]`);
    if (button) {
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
    }

    // Call API to start scraping
    fetch(`/api/scraping/structures/${structureId}/start-scraping/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        }
    })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to start scraping');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Show success message
                addAlert('success', `Started scraping for structure. Job ID: ${data.job_id || data.task_id}`);

                // Reset button after 2 seconds
                setTimeout(() => {
                    if (button) {
                        button.disabled = false;
                        button.innerHTML = '<i class="fas fa-robot"></i> Start Scraping';
                    }

                    // Redirect to scraping tab to see progress - Fix for the error
                    window.location.href = '/dashboard/#scraping';
                }, 2000);
            } else {
                throw new Error(data.message || 'Unknown error occurred');
            }
        })
        .catch(error => {
            console.error('Error starting scraping:', error);

            // Reset button
            if (button) {
                button.disabled = false;
                button.innerHTML = '<i class="fas fa-robot"></i> Start Scraping';
            }

            // Show error message
            addAlert('danger', `Failed to start scraping: ${error.message}`);
        });
}

function viewStructureDetails(structureId) {
    // Functionality to view structure details
    // This would typically open a modal with more information
    console.log('View structure', structureId);
    alert('Structure details functionality coming soon');
}

function getEntityTypeName(type) {
    const types = {
        'mairie': 'City Hall',
        'entreprise': 'Company',
        'b2b_lead': 'B2B Lead',
        'custom': 'Custom Structure'
    };
    return types[type] || type;
}

function getStrategyBadgeColor(strategy) {
    const colors = {
        'web_scraping': 'primary',
        'linkedin_scraping': 'linkedin',
        'api_scraping': 'success',
        'custom_scraping': 'info'
    };
    return colors[strategy] || 'secondary';
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString();
}

function addAlert(type, message) {
    const alertsContainer = document.getElementById('alertsContainer');
    if (!alertsContainer) return;

    const alertId = 'alert-' + Date.now();
    const alertHtml = `
        <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;

    alertsContainer.innerHTML += alertHtml;

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const alert = document.getElementById(alertId);
        if (alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }
    }, 5000);
}

function getCSRFToken() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
    return cookieValue;
} 