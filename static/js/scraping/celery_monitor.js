/**
 * Celery Worker Monitoring
 * Provides tools for monitoring Celery workers and tasks from the Django admin
 */

document.addEventListener('DOMContentLoaded', function () {
    console.log("Celery monitor initializing...");

    // Test Celery connection
    const testButton = document.getElementById('test-celery-connection');
    if (testButton) {
        console.log("Found test connection button, attaching event");
        testButton.addEventListener('click', function (e) {
            e.preventDefault();
            console.log("Test button clicked");
            testCeleryConnection();
        });
    } else {
        console.warn("Test celery connection button not found in the DOM");
    }

    // Refresh workers
    const refreshButton = document.getElementById('refresh-workers');
    if (refreshButton) {
        console.log("Found refresh button, attaching event");
        refreshButton.addEventListener('click', function (e) {
            e.preventDefault();
            console.log("Refresh button clicked");
            refreshWorkerStatus();
        });
    } else {
        console.warn("Refresh workers button not found in the DOM");
    }

    // Set up worker action buttons
    setupWorkerActions();

    // Setup tab actions
    setupTabActions();

    // Setup automatic scraping toggle
    const toggleBtn = document.getElementById('toggle-auto-scraping');
    if (toggleBtn) {
        console.log("Found toggle button, attaching event");
        toggleBtn.addEventListener('click', function (e) {
            e.preventDefault();
            console.log("Toggle button clicked");
            toggleAutomaticScraping();
        });
    } else {
        console.warn("Toggle auto-scraping button not found in the DOM");
    }

    console.log("Celery monitor initialization complete");
});

/**
 * Test Celery connection by sending an AJAX request
 */
function testCeleryConnection() {
    console.log("testCeleryConnection function called");

    const testButton = document.getElementById('test-celery-connection');
    const testResult = document.getElementById('test-result');

    if (!testButton || !testResult) {
        console.error("Button or result element not found");
        return;
    }

    // Disable button and show loading
    testButton.disabled = true;
    testButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Testing...';
    testResult.style.display = 'none';

    console.log('Sending test connection request...');
    console.log('CSRF Token:', getCookie('csrftoken'));

    // Send AJAX request with full URL path
    fetch('/admin/scraping/test-celery-connection/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({}), // Add empty body for POST request
        credentials: 'same-origin'
    })
        .then(response => {
            console.log('Response received:', response);
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Data received:', data);
            testButton.disabled = false;
            testButton.innerHTML = 'Test Celery Connection';
            testResult.style.display = 'inline';

            if (data.success) {
                testResult.innerHTML = '<span class="text-success">✓ Connection successful!</span>';
                if (data.result) {
                    testResult.innerHTML += ' Task executed on: ' + data.result.hostname;
                }
            } else {
                testResult.innerHTML = '<span class="text-danger">✗ Connection failed:</span> ' + data.error;
                console.error('Connection test failed:', data.error);
                if (data.traceback) {
                    console.error('Traceback:', data.traceback);
                }
            }
        })
        .catch(error => {
            console.error('Error during test connection:', error);
            testButton.disabled = false;
            testButton.innerHTML = 'Test Celery Connection';
            testResult.style.display = 'inline';
            testResult.innerHTML = '<span class="text-danger">✗ Request failed:</span> ' + error.message;
        });
}

/**
 * Set up worker action buttons
 */
function setupWorkerActions() {
    // Worker stats buttons
    const statButtons = document.querySelectorAll('.worker-stats');
    statButtons.forEach(button => {
        button.addEventListener('click', function () {
            const workerName = button.getAttribute('data-worker');
            showWorkerStats(workerName);
        });
    });

    // Worker shutdown buttons
    const shutdownButtons = document.querySelectorAll('.worker-shutdown');
    shutdownButtons.forEach(button => {
        button.addEventListener('click', function () {
            const workerName = button.getAttribute('data-worker');
            if (confirm('Are you sure you want to shut down worker ' + workerName + '?')) {
                shutdownWorker(workerName);
            }
        });
    });
}

/**
 * Show detailed stats for a worker
 */
function showWorkerStats(workerName) {
    // This would normally fetch stats from the server
    // For now, we'll just display a simple alert
    alert('Detailed stats for ' + workerName + ' would be shown here');

    // In a real implementation, you'd fetch stats and display them in a modal
    // fetch('/admin/scraping/worker-stats/' + encodeURIComponent(workerName) + '/')
    // .then(response => response.json())
    // .then(data => {
    //     // Display stats in modal
    // });
}

/**
 * Shutdown a worker
 */
function shutdownWorker(workerName) {
    // This would normally send a shutdown command to the server
    // For now, we'll just display a simple alert
    alert('Worker ' + workerName + ' shutdown command would be sent here');

    // In a real implementation:
    // fetch('/admin/scraping/shutdown-worker/' + encodeURIComponent(workerName) + '/', {
    //     method: 'POST',
    //     headers: {
    //         'X-CSRFToken': getCookie('csrftoken'),
    //         'Content-Type': 'application/json'
    //     }
    // })
    // .then(response => response.json())
    // .then(data => {
    //     if (data.success) {
    //         alert('Worker shutdown command sent successfully');
    //     } else {
    //         alert('Error shutting down worker: ' + data.error);
    //     }
    // });
}

/**
 * Setup tab actions
 */
function setupTabActions() {
    // Handle tab clicks
    const tabLinks = document.querySelectorAll('#workerTabs a[data-toggle="tab"]');
    tabLinks.forEach(tab => {
        tab.addEventListener('click', function (event) {
            event.preventDefault();

            // Hide all tab panes
            document.querySelectorAll('.tab-pane').forEach(pane => {
                pane.classList.remove('show', 'active');
            });

            // Show the target pane
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.classList.add('show', 'active');
            }

            // Deactivate all tabs
            tabLinks.forEach(t => {
                t.classList.remove('active');
            });

            // Activate this tab
            this.classList.add('active');

            // Load tab-specific content
            const tabId = this.getAttribute('href').substring(1);
            if (tabId === 'tasks') {
                loadActiveTasks();
            }
        });
    });

    // Set up task history loading
    const loadTasksBtn = document.getElementById('load-task-history');
    if (loadTasksBtn) {
        loadTasksBtn.addEventListener('click', loadTaskHistory);
    }

    // Set up worker logs loading
    const loadLogsBtn = document.getElementById('load-worker-logs');
    if (loadLogsBtn) {
        loadLogsBtn.addEventListener('click', loadWorkerLogs);
    }

    // Set up scraping logs loading
    const loadScrapingLogsBtn = document.getElementById('load-scraping-logs');
    if (loadScrapingLogsBtn) {
        loadScrapingLogsBtn.addEventListener('click', loadScrapingLogs);
    }
}

/**
 * Load active tasks
 */
function loadActiveTasks() {
    const container = document.getElementById('active-tasks-container');
    const loading = document.getElementById('loading-active-tasks');
    const list = document.getElementById('active-tasks-list');

    if (!container || !loading || !list) return;

    loading.style.display = 'block';
    list.style.display = 'none';

    // This would normally fetch data from the server
    // For now, we'll just simulate it with a timeout
    setTimeout(() => {
        loading.style.display = 'none';
        list.style.display = 'block';

        // Sample data - in a real implementation, this would come from the server
        const tasks = [
            { id: 'task-123', name: 'run_scraping_task', args: [42], started: '2023-04-25 10:15:30', worker: 'celery@LAPTOP-N2V4DS7N' },
            { id: 'task-124', name: 'start_structure_scrape', args: [7], started: '2023-04-25 10:17:45', worker: 'celery@LAPTOP-N2V4DS7N' }
        ];

        if (tasks.length === 0) {
            list.innerHTML = '<p class="text-center"><em>No active tasks found</em></p>';
        } else {
            let html = '<table class="table table-striped table-sm">';
            html += '<thead><tr><th>Task ID</th><th>Name</th><th>Arguments</th><th>Started</th><th>Worker</th><th>Actions</th></tr></thead>';
            html += '<tbody>';

            tasks.forEach(task => {
                html += `<tr>
                    <td>${task.id}</td>
                    <td>${task.name}</td>
                    <td>${JSON.stringify(task.args)}</td>
                    <td>${task.started}</td>
                    <td>${task.worker}</td>
                    <td><button class="btn btn-sm btn-danger revoke-task" data-task="${task.id}">Revoke</button></td>
                </tr>`;
            });

            html += '</tbody></table>';
            list.innerHTML = html;

            // Set up revoke buttons
            document.querySelectorAll('.revoke-task').forEach(button => {
                button.addEventListener('click', function () {
                    const taskId = button.getAttribute('data-task');
                    if (confirm('Are you sure you want to revoke task ' + taskId + '?')) {
                        alert('Task ' + taskId + ' would be revoked here');
                    }
                });
            });
        }
    }, 1000);
}

/**
 * Load task history
 */
function loadTaskHistory() {
    const container = document.getElementById('task-history-container');
    const loading = document.getElementById('loading-task-history');
    const list = document.getElementById('task-history-list');

    if (!container || !loading || !list) return;

    // Get filter values
    const taskType = document.getElementById('task-type-filter').value;
    const taskStatus = document.getElementById('task-status-filter').value;

    loading.style.display = 'block';
    list.style.display = 'none';

    // This would normally fetch data from the server with the filters
    // For now, we'll just simulate it with a timeout
    setTimeout(() => {
        loading.style.display = 'none';
        list.style.display = 'block';

        // Sample data - in a real implementation, this would come from the server
        const tasks = [
            { id: 'task-120', name: 'run_scraping_task', args: [40], status: 'SUCCESS', started: '2023-04-25 09:15:30', completed: '2023-04-25 09:20:45', result: 'Task completed with 25 leads found' },
            { id: 'task-121', name: 'start_structure_scrape', args: [5], status: 'FAILURE', started: '2023-04-25 09:25:30', completed: '2023-04-25 09:26:10', result: 'Error: Structure not found' },
            { id: 'task-122', name: 'test_celery_connection', args: [], status: 'SUCCESS', started: '2023-04-25 09:30:00', completed: '2023-04-25 09:30:01', result: 'Connection successful' }
        ];

        // Filter tasks based on selected filters
        let filteredTasks = tasks;
        if (taskType) {
            filteredTasks = filteredTasks.filter(task => task.name === taskType);
        }
        if (taskStatus) {
            filteredTasks = filteredTasks.filter(task => task.status === taskStatus);
        }

        if (filteredTasks.length === 0) {
            list.innerHTML = '<p class="text-center"><em>No tasks found matching the selected filters</em></p>';
        } else {
            let html = '<table class="table table-striped table-sm">';
            html += '<thead><tr><th>Task ID</th><th>Name</th><th>Arguments</th><th>Status</th><th>Started</th><th>Completed</th><th>Result</th></tr></thead>';
            html += '<tbody>';

            filteredTasks.forEach(task => {
                const statusClass = task.status === 'SUCCESS' ? 'text-success' : 'text-danger';
                html += `<tr>
                    <td>${task.id}</td>
                    <td>${task.name}</td>
                    <td>${JSON.stringify(task.args)}</td>
                    <td><span class="${statusClass}">${task.status}</span></td>
                    <td>${task.started}</td>
                    <td>${task.completed}</td>
                    <td>${task.result}</td>
                </tr>`;
            });

            html += '</tbody></table>';
            list.innerHTML = html;
        }
    }, 1000);
}

/**
 * Load worker logs
 */
function loadWorkerLogs() {
    const container = document.getElementById('worker-logs-container');
    const loading = document.getElementById('loading-worker-logs');
    const content = document.getElementById('worker-logs-content');

    if (!container || !loading || !content) return;

    // Get log level filter
    const logLevel = document.getElementById('log-level-filter').value;

    loading.style.display = 'block';
    content.style.display = 'none';

    // This would normally fetch data from the server
    // For now, we'll just simulate it with a timeout
    setTimeout(() => {
        loading.style.display = 'none';
        content.style.display = 'block';

        // Sample log data
        const logs = `[2023-04-25 10:00:15,123: INFO/ForkPoolWorker-1] Task scraping.tasks.test_celery_connection[1a2b3c] received
[2023-04-25 10:00:15,456: INFO/ForkPoolWorker-1] Test task received on worker LAPTOP-N2V4DS7N
[2023-04-25 10:00:15,789: INFO/ForkPoolWorker-1] Task scraping.tasks.test_celery_connection[1a2b3c] succeeded in 0.234s: {'status': 'success', 'message': 'Celery connection successful', 'timestamp': '2023-04-25T10:00:15.678', 'hostname': 'LAPTOP-N2V4DS7N'}
[2023-04-25 10:05:30,123: INFO/ForkPoolWorker-1] Task scraping.tasks.start_structure_scrape[4d5e6f] received
[2023-04-25 10:05:30,456: WARNING/ForkPoolWorker-1] Could not find structure with id 123
[2023-04-25 10:05:30,789: ERROR/ForkPoolWorker-1] Error starting manual scrape for structure 123: Structure matching query does not exist.
[2023-04-25 10:05:31,123: INFO/ForkPoolWorker-1] Task scraping.tasks.start_structure_scrape[4d5e6f] failed: Traceback (most recent call last):
  File "/path/to/tasks.py", line 42, in start_structure_scrape
    structure = ScrapingStructure.objects.get(id=structure_id)
  File "/path/to/django/db/models/manager.py", line 85, in manager_method
    return getattr(self.get_queryset(), name)(*args, **kwargs)
  File "/path/to/django/db/models/query.py", line 435, in get
    raise self.model.DoesNotExist(
scraping.models.ScrapingStructure.DoesNotExist: ScrapingStructure matching query does not exist.`;

        // Filter logs by level
        let filteredLogs = '';
        const lines = logs.split('\n');
        lines.forEach(line => {
            if (line.includes(`${logLevel}/`)) {
                filteredLogs += line + '\n';
            } else if (logLevel === 'ERROR' && line.includes('Traceback')) {
                filteredLogs += line + '\n';
            }
        });

        if (filteredLogs.trim() === '') {
            content.textContent = `No ${logLevel} level logs found.`;
        } else {
            content.textContent = filteredLogs;
        }
    }, 1000);
}

/**
 * Helper function to get cookie by name (for CSRF token)
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Load scraping logs for a specific task or all tasks
 */
function loadScrapingLogs() {
    const container = document.getElementById('scraping-logs-container');
    const loading = document.getElementById('loading-scraping-logs');
    const list = document.getElementById('scraping-logs-list');

    if (!container || !loading || !list) return;

    // Get filter values
    const taskId = document.getElementById('log-task-filter').value;
    const logType = document.getElementById('log-type-filter').value;

    loading.style.display = 'block';
    list.style.display = 'none';

    // Prepare the query parameters
    const params = new URLSearchParams();
    if (taskId) params.append('task_id', taskId);
    if (logType) params.append('log_type', logType);

    // Fetch the scraping logs from the server
    fetch(`/admin/scraping/scraping-logs/?${params.toString()}`, {
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
        .then(response => response.json())
        .then(data => {
            loading.style.display = 'none';
            list.style.display = 'block';

            if (!data.success) {
                list.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
                return;
            }

            const logs = data.logs;

            if (logs.length === 0) {
                list.innerHTML = '<p class="text-center"><em>No logs found matching the selected filters</em></p>';
                return;
            }

            // Render the logs
            let html = '';

            // Group logs by task for better organization
            const logsByTask = {};
            logs.forEach(log => {
                if (!logsByTask[log.task_id]) {
                    logsByTask[log.task_id] = [];
                }
                logsByTask[log.task_id].push(log);
            });

            // Render each task's logs
            Object.keys(logsByTask).forEach(taskId => {
                const taskLogs = logsByTask[taskId];
                const taskInfo = taskLogs[0].task_info || { job: { name: 'Unknown' } };

                html += `
                <div class="task-log-group mb-4">
                    <h4>Task #${taskId} - ${taskInfo.job?.name || 'Unknown Job'}</h4>
                    <div class="task-log-timeline">
            `;

                // Render each log in the task
                taskLogs.forEach(log => {
                    const logDate = new Date(log.timestamp);
                    const formattedDate = `${logDate.toLocaleDateString()} ${logDate.toLocaleTimeString()}`;

                    let logClass = '';
                    switch (log.log_type) {
                        case 'info': logClass = 'bg-info text-white'; break;
                        case 'warning': logClass = 'bg-warning'; break;
                        case 'error': logClass = 'bg-danger text-white'; break;
                        case 'success': logClass = 'bg-success text-white'; break;
                        case 'action': logClass = 'bg-primary text-white'; break;
                        default: logClass = 'bg-light';
                    }

                    html += `
                    <div class="log-entry mb-2">
                        <div class="log-header ${logClass}" style="padding: 8px; border-radius: 4px 4px 0 0;">
                            <strong>${log.log_type.toUpperCase()}</strong> - ${formattedDate}
                        </div>
                        <div class="log-body" style="padding: 8px; border: 1px solid #ddd; border-radius: 0 0 4px 4px;">
                            <p>${log.message}</p>
                `;

                    // Show details if available
                    if (log.details) {
                        let detailsHtml = '';
                        try {
                            // Try to parse details as JSON if it's a string
                            const details = typeof log.details === 'string'
                                ? JSON.parse(log.details)
                                : log.details;

                            // Special handling for lead details
                            if (details.lead) {
                                detailsHtml += '<div class="lead-details" style="background: #f9f9f9; padding: 8px; border-radius: 4px;">';
                                detailsHtml += '<h5>Lead Details:</h5>';
                                detailsHtml += '<ul>';
                                const lead = details.lead;
                                for (const key in lead) {
                                    detailsHtml += `<li><strong>${key}:</strong> ${lead[key]}</li>`;
                                }
                                detailsHtml += '</ul>';
                                detailsHtml += '</div>';
                            }
                            // Show traceback for errors
                            else if (details.traceback) {
                                detailsHtml += `<pre style="max-height: 200px; overflow-y: auto; background: #f5f5f5; padding: 8px; border-radius: 4px;">${details.traceback}</pre>`;
                            }
                            // Show other details
                            else {
                                detailsHtml += '<div class="details-table">';
                                detailsHtml += '<table style="width:100%;">';
                                for (const key in details) {
                                    const value = typeof details[key] === 'object'
                                        ? JSON.stringify(details[key])
                                        : details[key];
                                    detailsHtml += `<tr><td style="padding: 4px; border-bottom: 1px solid #eee;"><strong>${key}</strong></td><td style="padding: 4px; border-bottom: 1px solid #eee;">${value}</td></tr>`;
                                }
                                detailsHtml += '</table>';
                                detailsHtml += '</div>';
                            }

                            html += detailsHtml;
                        } catch (e) {
                            // Fallback if we can't parse details
                            html += `<pre>${JSON.stringify(log.details, null, 2)}</pre>`;
                        }
                    }

                    html += `
                        </div>
                    </div>
                `;
                });

                html += `
                    </div>
                </div>
            `;
            });

            list.innerHTML = html;
        })
        .catch(error => {
            loading.style.display = 'none';
            list.style.display = 'block';
            list.innerHTML = `<div class="alert alert-danger">Error loading logs: ${error.message}</div>`;
        });
}

/**
 * Toggle automatic scraping on/off
 */
function toggleAutomaticScraping() {
    console.log("toggleAutomaticScraping function called");

    const toggleBtn = document.getElementById('toggle-auto-scraping');
    if (!toggleBtn) {
        console.error("Toggle button not found");
        return;
    }

    const isEnabled = toggleBtn.getAttribute('data-enabled') === 'true';

    console.log('Toggling automatic scraping, current state:', isEnabled);
    console.log('CSRF Token:', getCookie('csrftoken'));

    // Disable button during request
    toggleBtn.disabled = true;
    toggleBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';

    // Send AJAX request
    fetch('/admin/scraping/toggle-automatic-scraping/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ enabled: !isEnabled }), // Send the opposite of current state
        credentials: 'same-origin'
    })
        .then(response => {
            console.log('Response received:', response);
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Data received:', data);

            // Re-enable button
            toggleBtn.disabled = false;

            if (data.success) {
                // Update button
                toggleBtn.innerText = data.enabled ? 'Disable Automatic Scraping' : 'Enable Automatic Scraping';
                toggleBtn.setAttribute('data-enabled', data.enabled.toString());

                // Update status badge
                const statusBadge = document.querySelector('span.status-badge');
                if (statusBadge) {
                    statusBadge.classList.remove('status-enabled', 'status-disabled');
                    statusBadge.classList.add(data.enabled ? 'status-enabled' : 'status-disabled');
                    statusBadge.innerText = data.enabled ? 'Enabled' : 'Disabled';
                }

                // Show success message
                alert(data.message);

                // Reload page to update task statuses
                window.location.reload();
            } else {
                console.error('Error in toggle response:', data.message);
                alert('Error: ' + data.message || 'Unknown error occurred');
            }
        })
        .catch(error => {
            console.error('Error toggling automatic scraping:', error);
            toggleBtn.disabled = false;
            toggleBtn.innerText = isEnabled ? 'Disable Automatic Scraping' : 'Enable Automatic Scraping';
            alert('Error: ' + error.message);
        });
}

/**
 * Refresh worker status via AJAX
 */
function refreshWorkerStatus() {
    const refreshButton = document.getElementById('refresh-workers');
    if (!refreshButton) return;

    // Disable button and show loading
    refreshButton.disabled = true;
    refreshButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Refreshing...';

    console.log('Sending refresh worker status request...');

    // Send AJAX request
    fetch('/admin/scraping/control-panel/', {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest', // Add this header to identify AJAX requests
            'Accept': 'application/json'
        }
    })
        .then(response => {
            console.log('Response received:', response);
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.text(); // Get the HTML response
        })
        .then(html => {
            console.log('HTML received, refreshing page...');
            // Since we're just replacing the whole page, a simple reload is fine
            window.location.reload();
        })
        .catch(error => {
            console.error('Error refreshing worker status:', error);
            refreshButton.disabled = false;
            refreshButton.innerHTML = '<i class="fas fa-sync"></i> Refresh';
            alert('Error refreshing worker status: ' + error.message);
        });
} 