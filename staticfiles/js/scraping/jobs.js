/**
 * Wizzy Scraping Jobs Module
 * Handles management of scraping tasks and jobs
 */

const WizzyScrapingJobs = {
    // Keep track of active and historical jobs
    jobs: {
        active: [],
        history: []
    },

    // Initialize the module
    init: function () {
        console.log('Initializing scraping jobs module');

        // Check authentication
        if (!WizzyUtils.isAuthenticated()) {
            return;
        }

        // Load active jobs
        this.loadActiveJobs();

        // Load job history
        this.loadJobHistory();

        // Set up event listeners
        this.setupEventListeners();
    },

    // Load active jobs from the API
    loadActiveJobs: async function () {
        try {
            // Show loading state
            const jobsContainer = document.getElementById('activeScrapingTasks');
            if (jobsContainer) {
                jobsContainer.innerHTML = `
                    <div class="text-center py-3">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Chargement...</span>
                        </div>
                        <p class="mt-2">Chargement des tâches en cours...</p>
                    </div>
                `;
            }

            // Use WizzyUtils.apiRequest to ensure JWT token is included
            const response = await WizzyUtils.apiRequest('/api/scraping/jobs/active/', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (response.ok) {
                const data = await response.json();
                console.log('Active jobs data:', data);

                // Store jobs in memory
                this.jobs.active = data.active_jobs || [];

                // Render the active jobs
                if (jobsContainer) {
                    if (!this.jobs.active || this.jobs.active.length === 0) {
                        jobsContainer.innerHTML = `
                            <div class="text-center py-3">
                                <div class="empty-state">
                                    <i class="fas fa-check-circle text-success fa-3x mb-3"></i>
                                    <p class="text-muted">
                                        Aucune tâche active pour le moment.
                                    </p>
                                    <button class="btn btn-primary mt-2" id="createNewTaskBtn">
                                        <i class="fas fa-plus me-2"></i> Créer une nouvelle tâche
                                    </button>
                                </div>
                            </div>
                        `;

                        // Re-attach event listener for the new button
                        const createNewTaskBtn = jobsContainer.querySelector('#createNewTaskBtn');
                        if (createNewTaskBtn) {
                            createNewTaskBtn.addEventListener('click', () => {
                                this.createNewJob();
                            });
                        }
                    } else {
                        // Render active jobs
                        let html = `<div class="row">`;

                        this.jobs.active.forEach(job => {
                            // Make sure job has task field
                            if (!job.task) {
                                job.task = {
                                    status: 'unknown',
                                    current_step: 'Waiting to start...',
                                    pages_explored: 0,
                                    leads_found: 0,
                                    unique_leads: 0,
                                    duration: 0
                                };
                            }

                            // Format dates
                            let startTime = 'N/A';
                            try {
                                if (job.task && job.task.start_time) {
                                    startTime = formatDateTime(job.task.start_time);
                                } else if (job.created_at) {
                                    startTime = formatDateTime(job.created_at);
                                }
                            } catch (e) {
                                console.error('Error formatting date:', e);
                            }

                            // Format progress
                            const progressColor = this.getProgressColor(job.status);
                            let progress = 0;

                            // Calculate progress based on task data if available
                            if (job.task) {
                                switch (job.task.status) {
                                    case 'initializing': progress = 10; break;
                                    case 'crawling': progress = 30; break;
                                    case 'extracting': progress = 60; break;
                                    case 'processing': progress = 80; break;
                                    case 'completed': progress = 100; break;
                                    default: progress = 10; break;
                                }
                            }

                            html += `
                                <div class="col-md-6 mb-3">
                                    <div class="card h-100">
                                        <div class="card-header d-flex justify-content-between align-items-center">
                                            <h6 class="mb-0">${job.name || 'Tâche sans nom'}</h6>
                                            <span class="badge ${this.getStatusBadgeClass(job.status)}">${this.getStatusLabel(job.status)}</span>
                                        </div>
                                        <div class="card-body">
                                            <div class="mb-3">
                                                <small class="text-muted">Progression:</small>
                                                <div class="progress mt-1" style="height: 6px;">
                                                    <div class="progress-bar ${progressColor}" role="progressbar" 
                                                        style="width: ${progress}%" 
                                                        aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100">
                                                    </div>
                                                </div>
                                                <div class="d-flex justify-content-between mt-1">
                                                    <small>${job.task ? job.task.current_step || 'En attente...' : 'En attente...'}</small>
                                                    <small>${progress}%</small>
                                                </div>
                                            </div>
                                            
                                            <div class="row mb-2">
                                                <div class="col-6">
                                                    <small class="text-muted">Structure:</small>
                                                    <p class="mb-0">${job.structure ? job.structure.name : 'Non spécifiée'}</p>
                                                </div>
                                                <div class="col-6">
                                                    <small class="text-muted">Leads trouvés:</small>
                                                    <p class="mb-0">${job.task ? job.task.leads_found || 0 : 0} (${job.task ? job.task.unique_leads || 0 : 0} uniques)</p>
                                                </div>
                                            </div>
                                            
                                            <div class="row">
                                                <div class="col-6">
                                                    <small class="text-muted">Démarré:</small>
                                                    <p class="mb-0">${startTime}</p>
                                                </div>
                                                <div class="col-6">
                                                    <small class="text-muted">Durée:</small>
                                                    <p class="mb-0">${job.task && job.task.duration ? formatDuration(job.task.duration) : 'En cours...'}</p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="card-footer">
                                            <div class="btn-group btn-group-sm">
                                                <button class="btn btn-outline-primary" onclick="WizzyScrapingJobs.viewJobDetails(${job.id})">
                                                    <i class="fas fa-eye me-1"></i> Détails
                                                </button>
                                                ${job.status === 'running' ? `
                                                    <button class="btn btn-outline-warning" onclick="WizzyScrapingJobs.pauseJob(${job.id})">
                                                        <i class="fas fa-pause me-1"></i> Pause
                                                    </button>
                                                ` : ''}
                                                ${job.status === 'paused' ? `
                                                    <button class="btn btn-outline-success" onclick="WizzyScrapingJobs.resumeJob(${job.id})">
                                                        <i class="fas fa-play me-1"></i> Reprendre
                                                    </button>
                                                ` : ''}
                                                ${(job.status === 'running' || job.status === 'paused') ? `
                                                    <button class="btn btn-outline-danger" onclick="WizzyScrapingJobs.stopJob(${job.id})">
                                                        <i class="fas fa-stop me-1"></i> Arrêter
                                                    </button>
                                                ` : ''}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            `;
                        });

                        html += `</div>`;
                        jobsContainer.innerHTML = html;
                    }
                }

                // Load worker activity after loading jobs
                this.loadWorkerActivity();
            } else {
                console.error('Failed to load active jobs');
                WizzyUtils.showAlert('Erreur lors du chargement des tâches actives', 'danger');

                if (jobsContainer) {
                    jobsContainer.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-circle me-2"></i>
                            Impossible de charger les tâches actives. Veuillez réessayer.
                        </div>
                    `;
                }
            }
        } catch (error) {
            console.error('Error loading active jobs:', error);
            WizzyUtils.showAlert('Erreur lors du chargement des tâches actives', 'danger');

            const jobsContainer = document.getElementById('activeScrapingTasks');
            if (jobsContainer) {
                jobsContainer.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        Erreur: ${error.message}
                    </div>
                `;
            }
        }
    },

    // Load job history from the API
    loadJobHistory: async function () {
        try {
            // Show loading state
            const historyContainer = document.getElementById('scrapingTasksHistory');
            if (historyContainer) {
                historyContainer.innerHTML = `
                    <div class="text-center py-3">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Chargement...</span>
                        </div>
                        <p class="mt-2">Chargement de l'historique...</p>
                    </div>
                `;
            }

            // Use WizzyUtils.apiRequest to ensure JWT token is included
            const response = await WizzyUtils.apiRequest('/api/scraping/jobs/history/', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (response.ok) {
                const data = await response.json();
                console.log('Job history data:', data);

                // Store jobs in memory
                this.jobs.history = data.jobs || [];

                // Render the job history
                if (historyContainer) {
                    if (!this.jobs.history || this.jobs.history.length === 0) {
                        historyContainer.innerHTML = `
                            <div class="text-center py-3">
                                <div class="empty-state">
                                    <i class="fas fa-history text-muted fa-3x mb-3"></i>
                                    <p class="text-muted">
                                        Aucun historique disponible.
                                    </p>
                                </div>
                            </div>
                        `;
                    } else {
                        // Render job history
                        let html = `<div class="table-responsive"><table class="table table-hover">`;
                        html += `
                            <thead>
                                <tr>
                                    <th>Nom</th>
                                    <th>Structure</th>
                                    <th>Statut</th>
                                    <th>Leads trouvés</th>
                                    <th>Date de création</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                        `;

                        this.jobs.history.forEach(job => {
                            html += this.renderJobHistoryRow(job);
                        });

                        html += `</tbody></table></div>`;
                        historyContainer.innerHTML = html;
                    }
                }
            } else {
                console.error('Failed to load job history:', response.status);
                if (historyContainer) {
                    historyContainer.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-circle"></i>
                            Erreur lors du chargement de l'historique.
                        </div>
                    `;
                }
            }
        } catch (error) {
            console.error('Error loading job history:', error);
            if (historyContainer) {
                historyContainer.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle"></i>
                        Une erreur est survenue lors du chargement de l'historique.
                    </div>
                `;
            }
        }
    },

    // Load worker activity from the API
    loadWorkerActivity: async function () {
        try {
            const activityContainer = document.getElementById('workerActivity');
            if (!activityContainer) return;

            // Show loading state
            activityContainer.innerHTML = `
                <div class="text-center py-3">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Chargement...</span>
                    </div>
                    <p class="mt-2">Chargement de l'activité des workers...</p>
                </div>
            `;

            // Use WizzyUtils.apiRequest to ensure JWT token is included
            const response = await WizzyUtils.apiRequest('/api/scraping/workers/activity/', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();

                // Update active workers count
                const countElement = document.getElementById('activeWorkersCount');
                if (countElement) {
                    countElement.textContent = `${data.active_workers || 0} actifs / ${data.total_workers || 0} total`;
                }

                // Render worker activities
                if (data.success && data.activities && data.activities.length > 0) {
                    let html = `
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead>
                                    <tr>
                                        <th>Worker</th>
                                        <th>Activité</th>
                                        <th>Status</th>
                                        <th>Tâche</th>
                                        <th>Dernière activité</th>
                                    </tr>
                                </thead>
                                <tbody>
                    `;

                    data.activities.forEach(activity => {
                        const statusClass = this.getStatusClass(activity.status);
                        const timeAgo = WizzyUtils.timeAgo(activity.timestamp);

                        html += `
                            <tr>
                                <td>
                                    <strong>${activity.worker_name}</strong>
                                    <div class="text-muted small">${activity.hostname}</div>
                                </td>
                                <td>${activity.activity_display || activity.activity_type}</td>
                                <td><span class="badge bg-${statusClass}">${activity.status_display || activity.status}</span></td>
                                <td>
                                    ${activity.task ?
                                `<a href="#" class="view-task" data-task-id="${activity.task.id}">
                                            ${activity.task.job_name || `Tâche #${activity.task.id}`}
                                        </a>
                                        <div class="text-muted small">${activity.current_url || ''}</div>`
                                : 'Aucune tâche'
                            }
                                </td>
                                <td>${timeAgo}</td>
                            </tr>
                        `;
                    });

                    html += `
                                </tbody>
                            </table>
                        </div>
                    `;

                    activityContainer.innerHTML = html;

                    // Add event listeners to view task buttons
                    document.querySelectorAll('.view-task').forEach(button => {
                        button.addEventListener('click', (e) => {
                            e.preventDefault();
                            const taskId = button.getAttribute('data-task-id');
                            this.viewTaskDetails(taskId);
                        });
                    });
                } else {
                    activityContainer.innerHTML = `
                        <div class="text-center py-3">
                            <div class="empty-state">
                                <i class="fas fa-robot fa-3x text-muted mb-3"></i>
                                <p class="text-muted">
                                    Aucun worker actif pour le moment.
                                    <br>Les workers seront visibles ici une fois les tâches de scraping lancées.
                                </p>
                            </div>
                        </div>
                    `;
                }
            } else {
                // Handle error
                console.error('Failed to load worker activity');
                activityContainer.innerHTML = `
                    <div class="alert alert-danger">
                        Impossible de charger l'activité des workers. Veuillez réessayer.
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error loading worker activity:', error);
            const activityContainer = document.getElementById('workerActivity');
            if (activityContainer) {
                activityContainer.innerHTML = `
                    <div class="alert alert-danger">
                        Erreur lors du chargement de l'activité des workers: ${error.message}
                    </div>
                `;
            }
        }
    },

    // Get status class for styling
    getStatusClass: function (status) {
        switch (status) {
            case 'running':
                return 'success';
            case 'idle':
                return 'secondary';
            case 'error':
                return 'danger';
            default:
                return 'info';
        }
    },

    // View task details
    viewTaskDetails: function (taskId) {
        // Implement task details view
        console.log('View task details for task ID:', taskId);
        // Could open a modal or navigate to a task details page
        // For now just show an alert
        alert(`Détails de la tâche #${taskId} - Fonctionnalité à venir`);
    },

    // Create a new scraping job for a structure
    createNewJob: function (structureId) {
        // Check if WizzyScrapingStructures exists
        if (typeof WizzyScrapingStructures === 'undefined' || !WizzyScrapingStructures.structures) {
            console.error("WizzyScrapingStructures is not defined or initialized");

            // Check if the structures.js script is already loaded
            const existingScript = document.querySelector('script[src*="scraping/structures.js"]');

            if (!existingScript) {
                console.log("Attempting to load structures.js script");
                // Add the script tag to load structures.js
                const script = document.createElement('script');
                script.src = '/static/js/scraping/structures.js';
                script.onload = () => {
                    console.log("Structures script loaded");
                    // Initialize WizzyScrapingStructures if available
                    if (typeof WizzyScrapingStructures !== 'undefined' && typeof WizzyScrapingStructures.init === 'function') {
                        WizzyScrapingStructures.init();
                        // Try again after a short delay to allow initialization to complete
                        setTimeout(() => this.createNewJob(structureId), 500);
                    } else {
                        WizzyUtils.showAlert('Erreur lors du chargement des structures', 'danger');
                    }
                };
                script.onerror = () => {
                    console.error("Failed to load structures script");
                    WizzyUtils.showAlert('Erreur lors du chargement des structures', 'danger');
                    this.createPlaceholderModal();
                };
                document.head.appendChild(script);
                return; // Exit and wait for script to load
            } else {
                // Script exists but module not initialized properly
                // Create a minimal version to prevent errors
                window.WizzyScrapingStructures = window.WizzyScrapingStructures || {
                    structures: [
                        {
                            id: 'placeholder1',
                            name: "Structure 1 (placeholder)",
                            entity_type: "custom"
                        },
                        {
                            id: 'placeholder2',
                            name: "Structure 2 (placeholder)",
                            entity_type: "custom"
                        }
                    ],
                    init: function () {
                        console.log('Using minimal WizzyScrapingStructures');
                        return this;
                    },
                    loadStructures: function () {
                        console.log('Using placeholder structures');
                        return this.structures;
                    }
                };
            }
        }

        // Create a modal for job creation
        const modalId = 'createJobModal';
        let modal = document.getElementById(modalId);

        // If modal doesn't exist, create it
        if (!modal) {
            const modalHtml = `
                <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="${modalId}Label" aria-hidden="true">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="${modalId}Label">Créer une nouvelle tâche de scraping</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                <form id="createJobForm">
                                    <div class="mb-3">
                                        <label for="structureSelect" class="form-label">Structure de scraping</label>
                                        <select class="form-select" id="structureSelect" required>
                                            <option value="">Sélectionner une structure</option>
                                        </select>
                                    </div>
                                    
                                    <div class="mb-3">
                                        <label for="jobTargetLeads" class="form-label">Nombre de leads cibles</label>
                                        <input type="number" class="form-control" id="jobTargetLeads" min="1" max="1000" value="10">
                                        <div class="form-text">Limite le nombre de leads que cette tâche va extraire</div>
                                    </div>
                                    
                                    <div class="mb-3">
                                        <label for="jobNotes" class="form-label">Notes (optionnel)</label>
                                        <textarea class="form-control" id="jobNotes" rows="2"></textarea>
                                    </div>
                                </form>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
                                <button type="button" class="btn btn-primary" id="submitJobBtn">
                                    <i class="fas fa-rocket"></i> Lancer la tâche
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Create a new div element to hold the modal
            const modalContainer = document.createElement('div');
            modalContainer.innerHTML = modalHtml;

            // Append the modal to the document body
            document.body.appendChild(modalContainer);

            // Now try to get the modal element
            modal = document.getElementById(modalId);

            // If still null, try a different approach
            if (!modal) {
                console.error("Modal creation failed using standard approach, trying alternate method");
                const modalElement = modalContainer.querySelector('.modal');
                if (modalElement) {
                    modalElement.id = modalId;
                    modal = modalElement;
                }
            }
        }

        // Check if modal exists before proceeding
        if (!modal) {
            console.error("Failed to create or find modal element");
            WizzyUtils.showAlert('Erreur lors de la création du formulaire', 'danger');
            return;
        }

        // Make sure Bootstrap is available
        if (typeof bootstrap === 'undefined' || !bootstrap.Modal) {
            console.error("Bootstrap or bootstrap.Modal is not available");

            // Try to load Bootstrap if not available
            if (!document.querySelector('script[src*="bootstrap"]')) {
                const script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js';
                document.head.appendChild(script);

                // Show an error message and suggest refresh
                WizzyUtils.showAlert('Bootstrap non disponible. Veuillez rafraîchir la page et réessayer.', 'warning');
                return;
            } else {
                WizzyUtils.showAlert('Erreur: Bootstrap non initialisé correctement', 'danger');
                return;
            }
        }

        // Find the structure if structureId is provided
        let selectedStructure = null;
        if (structureId && WizzyScrapingStructures.structures) {
            selectedStructure = WizzyScrapingStructures.structures.find(s => s.id.toString() === structureId.toString());
        }

        // Populate structure select
        const structureSelect = modal.querySelector('#structureSelect');
        if (structureSelect) {
            structureSelect.innerHTML = '<option value="">Sélectionner une structure</option>';

            if (WizzyScrapingStructures.structures && WizzyScrapingStructures.structures.length > 0) {
                WizzyScrapingStructures.structures.forEach(structure => {
                    const option = document.createElement('option');
                    option.value = structure.id;
                    option.textContent = structure.name;
                    structureSelect.appendChild(option);
                });
            } else {
                structureSelect.innerHTML += '<option value="placeholder" disabled>Aucune structure disponible</option>';
            }

            // Set selected structure if provided
            if (selectedStructure) {
                structureSelect.value = selectedStructure.id;
            }
        }

        // Set up form submission
        const submitBtn = modal.querySelector('#submitJobBtn');
        if (submitBtn) {
            submitBtn.onclick = () => {
                const form = modal.querySelector('#createJobForm');
                const structureId = modal.querySelector('#structureSelect').value;
                const targetLeads = modal.querySelector('#jobTargetLeads').value;
                const notes = modal.querySelector('#jobNotes').value;

                if (!structureId) {
                    alert('Veuillez sélectionner une structure');
                    return;
                }

                this.submitNewJob(structureId, targetLeads, notes);

                // Close the modal
                const bsModal = bootstrap.Modal.getInstance(modal);
                if (bsModal) {
                    bsModal.hide();
                }
            };
        }

        // Show the modal
        try {
            // First remove any existing modal backdrop if present
            const existingBackdrops = document.querySelectorAll('.modal-backdrop');
            existingBackdrops.forEach(backdrop => backdrop.remove());

            // Make sure the modal is in the DOM
            if (!document.body.contains(modal)) {
                document.body.appendChild(modal);
            }

            // Check if the modal is already initialized
            let bsModal = bootstrap.Modal.getInstance(modal);

            if (!bsModal) {
                // Initialize a new modal instance
                bsModal = new bootstrap.Modal(modal, {
                    backdrop: 'static',  // Prevent closing when clicking outside
                    keyboard: true       // Allow closing with Esc key
                });
            }

            // Show the modal
            bsModal.show();
        } catch (error) {
            console.error('Error showing modal:', error);
            WizzyUtils.showAlert('Erreur lors de l\'affichage du formulaire: ' + error.message, 'danger');
        }
    },

    // Create a simple placeholder modal when structures aren't available
    createPlaceholderModal: function () {
        const modalId = 'createJobModal';
        let modal = document.getElementById(modalId);

        // If modal doesn't exist, create it
        if (!modal) {
            const modalHtml = `
                <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="${modalId}Label" aria-hidden="true">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="${modalId}Label">Créer une nouvelle tâche de scraping</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                <div class="alert alert-warning">
                                    <i class="fas fa-exclamation-triangle me-2"></i>
                                    Impossible de charger les structures de scraping. Veuillez rafraîchir la page et réessayer.
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fermer</button>
                                <button type="button" class="btn btn-primary" onclick="location.reload()">
                                    <i class="fas fa-sync-alt"></i> Rafraîchir
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Create a new div element to hold the modal
            const modalContainer = document.createElement('div');
            modalContainer.innerHTML = modalHtml;

            // Append the modal to the document body
            document.body.appendChild(modalContainer);

            // Now try to get the modal element
            modal = document.getElementById(modalId);

            // If still null, try a different approach
            if (!modal) {
                console.error("Placeholder modal creation failed using standard approach, trying alternate method");
                const modalElement = modalContainer.querySelector('.modal');
                if (modalElement) {
                    modalElement.id = modalId;
                    modal = modalElement;
                }
            }
        }

        // Check if modal exists before proceeding
        if (!modal) {
            console.error("Failed to create or find placeholder modal element");
            WizzyUtils.showAlert('Erreur lors de la création du formulaire de secours', 'danger');
            return;
        }

        // Make sure Bootstrap is available
        if (typeof bootstrap === 'undefined' || !bootstrap.Modal) {
            console.error("Bootstrap or bootstrap.Modal is not available for placeholder modal");

            // Try to load Bootstrap if not available
            if (!document.querySelector('script[src*="bootstrap"]')) {
                const script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js';
                document.head.appendChild(script);

                // Show an error message directly since we can't show a modal
                alert('Bootstrap non disponible. Veuillez rafraîchir la page et réessayer.');
                return;
            } else {
                alert('Erreur: Bootstrap non initialisé correctement. Veuillez rafraîchir la page.');
                return;
            }
        }

        try {
            // First remove any existing modal backdrop if present
            const existingBackdrops = document.querySelectorAll('.modal-backdrop');
            existingBackdrops.forEach(backdrop => backdrop.remove());

            // Make sure the modal is in the DOM
            if (!document.body.contains(modal)) {
                document.body.appendChild(modal);
            }

            // Check if the modal is already initialized
            let bsModal = bootstrap.Modal.getInstance(modal);

            if (!bsModal) {
                // Initialize a new modal instance
                bsModal = new bootstrap.Modal(modal, {
                    backdrop: 'static',
                    keyboard: true
                });
            }

            // Show the modal
            bsModal.show();
        } catch (error) {
            console.error('Error showing placeholder modal:', error);
            // Use a simple alert as fallback
            alert('Erreur lors de l\'affichage du formulaire: ' + error.message);
        }
    },

    // Submit a new job to the API
    submitNewJob: async function (structureId, targetLeads, notes) {
        try {
            // Get structure name for better job naming
            let structureName = `Structure #${structureId}`;
            if (WizzyScrapingStructures && WizzyScrapingStructures.structures) {
                const structure = WizzyScrapingStructures.structures.find(s => s.id.toString() === structureId.toString());
                if (structure) {
                    structureName = structure.name;
                }
            }

            // Make the actual API call to create job using WizzyUtils.apiRequest
            const response = await WizzyUtils.apiRequest('/api/scraping/jobs/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: `Manual scrape: ${structureName}`,
                    structure_id: structureId,
                    search_query: `manual_${structureId}_${new Date().getTime()}`,
                    leads_allocated: parseInt(targetLeads) || 10,
                    notes: notes || ''
                })
            });

            const data = await response.json();

            if (response.ok && data.success) {
                // Show success message with job ID
                WizzyUtils.showAlert(`Tâche créée avec succès (ID: ${data.job_id})`, 'success');

                // Refresh active jobs list
                this.loadActiveJobs();

                // Set up auto-refresh to see task progress
                let refreshCount = 0;
                const refreshInterval = setInterval(() => {
                    this.loadActiveJobs();
                    this.loadWorkerActivity();
                    refreshCount++;

                    // Stop auto-refresh after 5 times (50 seconds)
                    if (refreshCount >= 5) {
                        clearInterval(refreshInterval);
                    }
                }, 10000); // Refresh every 10 seconds

                return true;
            } else {
                // Show error message
                WizzyUtils.showAlert(data.error || 'Erreur lors de la création de la tâche', 'danger');
                return false;
            }
        } catch (error) {
            console.error('Error creating job:', error);
            WizzyUtils.showAlert(`Erreur lors de la création de la tâche: ${error.message}`, 'danger');
            return false;
        }
    },

    // Setup event listeners
    setupEventListeners: function () {
        const createNewTaskBtn = document.getElementById('createNewTaskBtn');
        if (createNewTaskBtn) {
            createNewTaskBtn.addEventListener('click', () => {
                this.createNewJob();
            });
        }
    },

    // Get status badge class for styling
    getStatusBadgeClass: function (status) {
        switch (status) {
            case 'initializing': return 'bg-info';
            case 'running': return 'bg-primary';
            case 'completed': return 'bg-success';
            case 'failed': return 'bg-danger';
            case 'paused': return 'bg-warning';
            default: return 'bg-secondary';
        }
    },

    // Get status label
    getStatusLabel: function (status) {
        switch (status) {
            case 'initializing': return 'Initialisation';
            case 'running': return 'En cours';
            case 'completed': return 'Terminé';
            case 'failed': return 'Échoué';
            case 'paused': return 'En pause';
            default: return status;
        }
    },

    // Get progress bar color based on status
    getProgressColor: function (status) {
        switch (status) {
            case 'completed': return 'bg-success';
            case 'failed': return 'bg-danger';
            case 'paused': return 'bg-warning';
            default: return 'bg-primary';
        }
    },

    // View job details
    viewJobDetails: function (jobId) {
        console.log('View job details for job ID:', jobId);

        // Show loading message
        WizzyUtils.showAlert('Chargement des détails...', 'info');

        // Use WizzyUtils.apiRequest to ensure JWT token is included
        WizzyUtils.apiRequest(`/api/scraping/jobs/${jobId}/`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success && data.job) {
                    // Display job details in modal
                    this.showJobDetailsModal(data.job);
                } else {
                    // Handle error in response
                    throw new Error(data.error || 'Tâche non trouvée');
                }
            })
            .catch(error => {
                console.error('Error fetching job details:', error);
                WizzyUtils.showAlert(`Erreur: ${error.message}`, 'danger');
            });
    },

    // Show job details modal
    showJobDetailsModal: function (job) {
        // Make sure job has task field
        if (!job.task) {
            job.task = {
                status: 'unknown',
                current_step: 'Waiting to start...',
                pages_explored: 0,
                leads_found: 0,
                unique_leads: 0,
                duration: 0
            };
        }

        // Format dates
        let startTime = 'N/A';
        try {
            if (job.task && job.task.start_time) {
                startTime = formatDateTime(job.task.start_time);
            } else if (job.created_at) {
                startTime = formatDateTime(job.created_at);
            }
        } catch (e) {
            console.error('Error formatting date:', e);
        }

        // Create modal content
        const progressColor = this.getProgressColor(job.status);

        // Calculate progress based on task status
        let progress = 0;
        let currentStep = 'En attente...';

        if (job.task) {
            currentStep = job.task.current_step || 'En attente...';

            switch (job.task.status) {
                case 'initializing': progress = 10; break;
                case 'crawling': progress = 30; break;
                case 'extracting': progress = 60; break;
                case 'processing': progress = 80; break;
                case 'completed': progress = 100; break;
                default: progress = 10; break;
            }
        }

        const content = `
            <div class="job-details">
                <div class="row mb-4">
                    <div class="col-md-6">
                        <p><strong>Structure:</strong> ${job.structure ? job.structure.name : 'Non spécifiée'}</p>
                        <p><strong>Démarré le:</strong> ${startTime}</p>
                        <p><strong>Durée:</strong> ${job.task && job.task.duration ? formatDuration(job.task.duration) : 'En cours...'}</p>
                    </div>
                    <div class="col-md-6">
                        <p><strong>Status:</strong> <span class="badge ${this.getStatusBadgeClass(job.status)}">${this.getStatusLabel(job.status)}</span></p>
                        <p><strong>Leads trouvés:</strong> ${job.task ? job.task.leads_found || 0 : 0} (${job.task ? job.task.unique_leads || 0 : 0} uniques)</p>
                        <p><strong>Pages explorées:</strong> ${job.task ? job.task.pages_explored || 0 : 0}</p>
                    </div>
                </div>
                
                <div class="mb-4">
                    <h6>Progression</h6>
                    <div class="progress mb-2" style="height: 8px;">
                        <div class="progress-bar ${progressColor}" role="progressbar" 
                            style="width: ${progress}%" 
                            aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100">
                        </div>
                    </div>
                    <div class="d-flex justify-content-between">
                        <small>${currentStep}</small>
                        <small>${progress}%</small>
                    </div>
                </div>
                
                <div class="mb-4">
                    <h6>Détails de la tâche</h6>
                    <p><strong>Nom:</strong> ${job.name || 'Sans nom'}</p>
                    <p><strong>Recherche:</strong> ${job.search_query || 'Non spécifié'}</p>
                    <p><strong>Leads alloués:</strong> ${job.leads_allocated || 0}</p>
                    ${job.task_source ? `<p><strong>Source de la tâche:</strong> ${job.task_source}</p>` : ''}
                </div>
                
                <div class="mb-4">
                    <h6>Détails de l'exécution</h6>
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>État</th>
                                    <th>Détails</th>
                                    <th>Dernière activité</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${job.task ? `
                                    <tr>
                                        <td><span class="badge ${this.getStatusBadgeClass(job.task.status)}">${this.getStatusLabel(job.task.status)}</span></td>
                                        <td>${job.task.current_step || 'En cours...'}</td>
                                        <td>${job.task.last_activity ? formatDateTime(job.task.last_activity) : (job.updated_at ? formatDateTime(job.updated_at) : 'N/A')}</td>
                                    </tr>
                                    ${job.task.error_message ? `
                                    <tr>
                                        <td colspan="3" class="text-danger">
                                            <i class="fas fa-exclamation-circle me-1"></i> 
                                            Erreur: ${job.task.error_message}
                                        </td>
                                    </tr>
                                    ` : ''}
                                ` : `
                                    <tr>
                                        <td colspan="3" class="text-center">Aucune information d'exécution disponible</td>
                                    </tr>
                                `}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

        // Create the modal
        const modalId = 'jobDetailsModal';
        let modal = document.getElementById(modalId);

        // If modal exists, remove it to avoid duplicates
        if (modal) {
            modal.remove();
        }

        // Create modal HTML
        const modalHtml = `
            <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="${modalId}Label" aria-hidden="true">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="${modalId}Label">Détails de la tâche #${job.id}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            ${content}
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fermer</button>
                            ${job.status === 'running' ? `
                                <button type="button" class="btn btn-warning" onclick="WizzyScrapingJobs.pauseJob(${job.id})">
                                    <i class="fas fa-pause me-1"></i> Mettre en pause
                                </button>
                            ` : ''}
                            ${job.status === 'paused' ? `
                                <button type="button" class="btn btn-success" onclick="WizzyScrapingJobs.resumeJob(${job.id})">
                                    <i class="fas fa-play me-1"></i> Reprendre
                                </button>
                            ` : ''}
                            ${(job.status === 'running' || job.status === 'paused') ? `
                                <button type="button" class="btn btn-danger" onclick="WizzyScrapingJobs.stopJob(${job.id})">
                                    <i class="fas fa-stop me-1"></i> Arrêter
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Create modal element
        const modalContainer = document.createElement('div');
        modalContainer.innerHTML = modalHtml;
        document.body.appendChild(modalContainer.firstChild);

        // Get the modal element
        modal = document.getElementById(modalId);

        // Fix: Check if bootstrap is available and delay modal initialization if needed
        if (typeof bootstrap === 'undefined' || !bootstrap.Modal) {
            console.warn("Bootstrap not found, attempting to load it dynamically");

            // Try to load Bootstrap dynamically
            const bootstrapScript = document.createElement('script');
            bootstrapScript.src = 'https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js';
            bootstrapScript.onload = () => {
                console.log("Bootstrap loaded dynamically");
                // Now that Bootstrap is loaded, show the modal
                setTimeout(() => {
                    try {
                        const bsModal = new bootstrap.Modal(modal);
                        bsModal.show();
                    } catch (err) {
                        console.error("Error showing modal after dynamic loading:", err);
                        WizzyUtils.showAlert("Impossible d'afficher les détails. Veuillez rafraîchir la page et réessayer.", 'warning');
                    }
                }, 500); // Wait a bit for Bootstrap to initialize
            };
            bootstrapScript.onerror = () => {
                console.error("Failed to load Bootstrap dynamically");
                WizzyUtils.showAlert("Impossible d'afficher les détails. Veuillez rafraîchir la page et réessayer.", 'warning');
            };
            document.head.appendChild(bootstrapScript);
        } else {
            // Bootstrap is available, show the modal
            try {
                const bsModal = new bootstrap.Modal(modal);
                bsModal.show();
            } catch (err) {
                console.error("Error showing modal:", err);
                WizzyUtils.showAlert("Erreur lors de l'affichage des détails.", 'warning');

                // Handle the case where the modal can't be shown
                let errMsg = `<div class="alert alert-warning">
                    <strong>Impossible d'afficher le modal.</strong><br>
                    Voici les détails de la tâche #${job.id}:<br>
                    - Nom: ${job.name}<br>
                    - Structure: ${job.structure ? job.structure.name : 'Non spécifiée'}<br>
                    - Statut: ${this.getStatusLabel(job.status)}<br>
                    - Leads trouvés: ${job.task ? job.task.leads_found || 0 : 0}<br>
                </div>`;
                WizzyUtils.showAlert(errMsg, 'info', 10000); // Show for 10 seconds
            }
        }
    },

    // Pause a job
    pauseJob: function (jobId) {
        this.controlJob(jobId, 'pause');
    },

    // Resume a paused job
    resumeJob: function (jobId) {
        this.controlJob(jobId, 'resume');
    },

    // Stop a job
    stopJob: function (jobId) {
        if (confirm('Êtes-vous sûr de vouloir arrêter cette tâche ? Cette action est irréversible.')) {
            this.controlJob(jobId, 'stop');
        }
    },

    // Generic job control function (pause, resume, stop)
    controlJob: async function (jobId, action) {
        try {
            // Show loading message
            WizzyUtils.showAlert(`${this.getActionVerb(action)} la tâche en cours...`, 'info');

            // Use WizzyUtils.apiRequest to ensure JWT token is included
            const response = await WizzyUtils.apiRequest(`/api/scraping/jobs/${jobId}/control/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ action: action })
            });

            if (response.ok) {
                const data = await response.json();

                if (data.success) {
                    // Show success message
                    WizzyUtils.showAlert(`Tâche ${this.getActionLabel(action)} avec succès`, 'success');

                    // Close details modal if open
                    const detailsModal = document.getElementById('jobDetailsModal');
                    if (detailsModal) {
                        const bsModal = bootstrap.Modal.getInstance(detailsModal);
                        if (bsModal) {
                            bsModal.hide();
                        }
                    }

                    // Refresh active jobs to see updated status
                    this.loadActiveJobs();
                    return true;
                } else {
                    WizzyUtils.showAlert(data.error || `Erreur lors de l'action ${action}`, 'danger');
                    return false;
                }
            } else {
                WizzyUtils.showAlert(`Erreur lors de l'action ${action}`, 'danger');
                return false;
            }
        } catch (error) {
            console.error(`Error ${action} job:`, error);
            WizzyUtils.showAlert(`Erreur lors de l'action ${action}: ${error.message}`, 'danger');
            return false;
        }
    },

    // Get action verb based on the control action
    getActionVerb: function (action) {
        switch (action) {
            case 'pause': return 'Mise en pause de';
            case 'resume': return 'Reprise de';
            case 'stop': return 'Arrêt de';
            default: return 'Contrôle de';
        }
    },

    // Get action label based on the control action
    getActionLabel: function (action) {
        switch (action) {
            case 'pause': return 'mise en pause';
            case 'resume': return 'reprise';
            case 'stop': return 'arrêtée';
            default: return action;
        }
    },

    // Restart a job
    restartJob: function (jobId) {
        if (confirm('Êtes-vous sûr de vouloir redémarrer cette tâche ?')) {
            this.controlJob(jobId, 'restart');
        }
    }
};

// Scraping Jobs Management
document.addEventListener('DOMContentLoaded', function () {
    // Initialize UI if on scraping tab
    if (document.querySelector('#scraping-tab')) {
        // Check if WizzyScrapingJobs is being used directly
        if (typeof WizzyScrapingJobs !== 'undefined' && typeof WizzyScrapingJobs.init === 'function') {
            console.log('Initializing WizzyScrapingJobs from module');
            WizzyScrapingJobs.init();
        } else {
            console.log('Initializing scraping UI from legacy functions');
            initScrapingUI();
            loadActiveScrapingTasks();
            loadScrapingTasksHistory();

            // Set up periodic refresh for active tasks
            setInterval(function () {
                loadActiveScrapingTasks();
            }, 10000); // Refresh every 10 seconds
        }

        // Check and init structures module if available but not initialized
        if (typeof WizzyScrapingStructures !== 'undefined' && typeof WizzyScrapingStructures.init === 'function'
            && (!WizzyScrapingStructures.structures || WizzyScrapingStructures.structures.length === 0)) {
            console.log('Initializing WizzyScrapingStructures from jobs.js');
            WizzyScrapingStructures.init();
        }
    }
});

// Initialize UI elements
function initScrapingUI() {
    const createNewTaskBtn = document.getElementById('createNewTaskBtn');
    if (createNewTaskBtn) {
        createNewTaskBtn.addEventListener('click', function () {
            showCreateTaskModal();
        });
    }
}

// Load active scraping tasks
function loadActiveScrapingTasks() {
    const container = document.getElementById('activeScrapingTasks');
    if (!container) return;

    // Add loading indicator
    container.innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <span class="ms-2">Chargement des tâches en cours...</span>
        </div>
    `;

    // Fetch active tasks from API
    fetch('/api/tasks/active/')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Ensure data is in the expected format
            if (data && !Array.isArray(data)) {
                // If data is not an array, check if it has a tasks property
                if (data.tasks && Array.isArray(data.tasks)) {
                    renderActiveTasks(container, data.tasks);
                } else {
                    // Create an empty array if no valid data format is found
                    renderActiveTasks(container, []);
                }
            } else {
                renderActiveTasks(container, data);
            }
        })
        .catch(error => {
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    Erreur lors du chargement des tâches: ${error.message}
                </div>
            `;
        });
}

// Render active tasks
function renderActiveTasks(container, tasks) {
    // Check if tasks is an array
    if (!tasks || !Array.isArray(tasks) || tasks.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4">
                <i class="fas fa-check-circle text-success fa-2x mb-3"></i>
                <p>Aucune tâche en cours actuellement.</p>
                <button class="btn btn-primary btn-sm" onclick="showCreateTaskModal()">
                    <i class="fas fa-plus me-1"></i> Démarrer une nouvelle tâche
                </button>
            </div>
        `;
        return;
    }

    let html = `<div class="row">`;

    tasks.forEach(task => {
        // Format progress bar color based on status
        let progressColor = 'bg-primary';
        if (task.status === 'completed') progressColor = 'bg-success';
        if (task.status === 'failed') progressColor = 'bg-danger';
        if (task.status === 'paused') progressColor = 'bg-warning';

        html += `
            <div class="col-md-6 mb-3">
                <div class="card h-100">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h6 class="mb-0">${task.job_name}</h6>
                        <span class="badge ${getStatusBadgeClass(task.status)}">${getStatusLabel(task.status)}</span>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <small class="text-muted">Progression:</small>
                            <div class="progress mt-1" style="height: 6px;">
                                <div class="progress-bar ${progressColor}" role="progressbar" 
                                    style="width: ${task.progress_percentage}%" 
                                    aria-valuenow="${task.progress_percentage}" aria-valuemin="0" aria-valuemax="100">
                                </div>
                            </div>
                            <div class="d-flex justify-content-between mt-1">
                                <small>${task.current_step || 'En attente...'}</small>
                                <small>${task.progress_percentage}%</small>
                            </div>
                        </div>
                        
                        <div class="row mb-2">
                            <div class="col-6">
                                <small class="text-muted">Pages explorées:</small>
                                <p class="mb-0">${task.pages_explored}</p>
                            </div>
                            <div class="col-6">
                                <small class="text-muted">Leads trouvés:</small>
                                <p class="mb-0">${task.leads_found} (${task.unique_leads} uniques)</p>
                            </div>
                        </div>
                        
                        <div class="row">
                            <div class="col-6">
                                <small class="text-muted">Démarré:</small>
                                <p class="mb-0">${formatDateTime(task.start_time)}</p>
                            </div>
                            <div class="col-6">
                                <small class="text-muted">Durée:</small>
                                <p class="mb-0">${formatDuration(task.duration)}</p>
                            </div>
                        </div>
                    </div>
                    <div class="card-footer">
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-primary" onclick="viewTaskDetails(${task.id})">
                                <i class="fas fa-eye me-1"></i> Détails
                            </button>
                            <button class="btn btn-outline-secondary" onclick="viewTaskResults(${task.id})">
                                <i class="fas fa-list me-1"></i> Résultats
                            </button>
                            ${task.status === 'running' ? `
                                <button class="btn btn-outline-warning" onclick="pauseTask(${task.id})">
                                    <i class="fas fa-pause me-1"></i> Pause
                                </button>
                            ` : ''}
                            ${task.status === 'paused' ? `
                                <button class="btn btn-outline-success" onclick="resumeTask(${task.id})">
                                    <i class="fas fa-play me-1"></i> Reprendre
                                </button>
                            ` : ''}
                            ${(task.status === 'running' || task.status === 'paused') ? `
                                <button class="btn btn-outline-danger" onclick="stopTask(${task.id})">
                                    <i class="fas fa-stop me-1"></i> Arrêter
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    });

    html += `</div>`;
    container.innerHTML = html;
}

// Load tasks history
function loadScrapingTasksHistory() {
    const container = document.getElementById('scrapingTasksHistory');
    if (!container) return;

    // Add loading indicator
    container.innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <span class="ms-2">Chargement de l'historique...</span>
        </div>
    `;

    // Fetch task history from API
    fetch('/api/tasks/history/')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Ensure data is in the expected format
            if (data && !Array.isArray(data)) {
                // If data is not an array, check if it has a history property
                if (data.history && Array.isArray(data.history)) {
                    renderTasksHistory(container, data.history);
                } else {
                    // Create an empty array if no valid data format is found
                    renderTasksHistory(container, []);
                }
            } else {
                renderTasksHistory(container, data);
            }
        })
        .catch(error => {
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    Erreur lors du chargement de l'historique: ${error.message}
                </div>
            `;
        });
}

// Render tasks history
function renderTasksHistory(container, tasks) {
    // Check if tasks is an array
    if (!tasks || !Array.isArray(tasks) || tasks.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4">
                <i class="fas fa-history text-muted fa-2x mb-3"></i>
                <p>Aucune tâche terminée dans l'historique.</p>
            </div>
        `;
        return;
    }

    let html = `
        <div class="table-responsive">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Tâche</th>
                        <th>Structure</th>
                        <th>Statut</th>
                        <th>Leads</th>
                        <th>Durée</th>
                        <th>Date</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
    `;

    tasks.forEach(task => {
        html += `
            <tr>
                <td>${task.job_name}</td>
                <td>${task.structure_name}</td>
                <td><span class="badge ${getStatusBadgeClass(task.status)}">${getStatusLabel(task.status)}</span></td>
                <td>${task.unique_leads} / ${task.leads_found}</td>
                <td>${formatDuration(task.duration)}</td>
                <td>${formatDateTime(task.completion_time)}</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-sm btn-outline-primary" onclick="viewTaskDetails(${task.id})">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-secondary" onclick="viewTaskResults(${task.id})">
                            <i class="fas fa-list"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-success" onclick="restartTask(${task.job_id})">
                            <i class="fas fa-redo"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });

    html += `
                </tbody>
            </table>
        </div>
    `;

    container.innerHTML = html;
}

// View task details
function viewTaskDetails(taskId) {
    window.location.href = `/scraping/task/${taskId}/`;
}

// View task results
function viewTaskResults(taskId) {
    window.location.href = `/scraping/task/${taskId}/results/`;
}

// Pause task
function pauseTask(taskId) {
    controlTask(taskId, 'pause');
}

// Resume task
function resumeTask(taskId) {
    controlTask(taskId, 'resume');
}

// Stop task
function stopTask(taskId) {
    if (confirm('Êtes-vous sûr de vouloir arrêter cette tâche ? Cette action est irréversible.')) {
        controlTask(taskId, 'stop');
    }
}

// Restart task
function restartTask(jobId) {
    if (confirm('Êtes-vous sûr de vouloir redémarrer cette tâche ?')) {
        fetch(`/api/jobs/${jobId}/start/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            }
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                showNotification('success', 'Tâche redémarrée avec succès');
                loadActiveScrapingTasks();
            })
            .catch(error => {
                showNotification('error', `Erreur lors du redémarrage de la tâche: ${error.message}`);
            });
    }
}

// Control task (pause, resume, stop)
function controlTask(taskId, action) {
    fetch(`/api/tasks/${taskId}/control/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ action: action })
    })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            showNotification('success', `Tâche ${getActionLabel(action)} avec succès`);
            loadActiveScrapingTasks();
        })
        .catch(error => {
            showNotification('error', `Erreur lors du contrôle de la tâche: ${error.message}`);
        });
}

// Show create task modal
function showCreateTaskModal() {
    // Implementation will depend on your modal system
    // For now, just redirect to the create page
    window.location.href = '/scraping/create/';
}

// Get CSRF token
function getCsrfToken() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
    return cookieValue;
}

// Show notification
function showNotification(type, message) {
    const alertsContainer = document.getElementById('alertsContainer');
    if (!alertsContainer) return;

    const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
    const icon = type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle';

    const alertHtml = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            <i class="fas ${icon} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;

    alertsContainer.innerHTML = alertHtml + alertsContainer.innerHTML;

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const alerts = alertsContainer.getElementsByClassName('alert');
        if (alerts.length > 0) {
            const alertToRemove = alerts[alerts.length - 1];
            alertToRemove.classList.remove('show');
            setTimeout(() => {
                alertToRemove.remove();
            }, 150);
        }
    }, 5000);
}

// Helper functions
function getStatusBadgeClass(status) {
    switch (status) {
        case 'initializing': return 'bg-info';
        case 'crawling':
        case 'extracting':
        case 'processing':
        case 'running': return 'bg-primary';
        case 'paused': return 'bg-warning';
        case 'completed': return 'bg-success';
        case 'failed': return 'bg-danger';
        default: return 'bg-secondary';
    }
}

function getStatusLabel(status) {
    switch (status) {
        case 'initializing': return 'Initialisation';
        case 'crawling': return 'Exploration';
        case 'extracting': return 'Extraction';
        case 'processing': return 'Traitement';
        case 'running': return 'En cours';
        case 'paused': return 'En pause';
        case 'completed': return 'Terminé';
        case 'failed': return 'Échoué';
        default: return status;
    }
}

function getActionLabel(action) {
    switch (action) {
        case 'pause': return 'mise en pause';
        case 'resume': return 'reprise';
        case 'stop': return 'arrêtée';
        default: return action;
    }
}

function formatDateTime(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatDuration(seconds) {
    if (!seconds) return 'N/A';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    let result = '';
    if (hours > 0) result += `${hours}h `;
    if (minutes > 0 || hours > 0) result += `${minutes}m `;
    result += `${secs}s`;

    return result.trim();
}

// For direct access from another page or tab
window.launchScrapingTask = function (structureId) {
    // Make sure WizzyScrapingJobs is initialized
    if (typeof WizzyScrapingJobs === 'undefined') {
        console.error("WizzyScrapingJobs is not defined");
        alert("Erreur: Module de tâches non disponible");
        return;
    }

    // If on another tab, navigate to the scraping tab first
    const scrapingTab = document.querySelector('#scraping-tab');
    if (scrapingTab && !scrapingTab.classList.contains('active')) {
        // Trigger a click on the scraping tab first
        scrapingTab.click();

        // Wait for tab to be active before continuing
        setTimeout(() => {
            WizzyScrapingJobs.createNewJob(structureId);
        }, 300);
    } else {
        // Already on scraping tab, create job directly
        WizzyScrapingJobs.createNewJob(structureId);
    }
};

// Make the module available globally
window.WizzyScrapingJobs = WizzyScrapingJobs; 