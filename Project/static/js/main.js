document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const loader = document.getElementById('loader');
    const resultsSection = document.querySelector('.results-section');
    let currentReport = null;
    let sessionId = 'chat1';  // Consistent with the notebook implementation

    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            
            button.classList.add('active');
            const targetTab = document.getElementById(button.dataset.tab);
            targetTab.classList.add('active');
        });
    });

    // File upload handling
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const fileInput = document.getElementById('reportFile');
        const file = fileInput.files[0];
        
        if (!file) {
            alert('Please select a file');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        loader.style.display = 'block';
        resultsSection.style.display = 'none';

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            currentReport = data.report;
            displayResults(data);
            resultsSection.style.display = 'block';
        } catch (error) {
            alert('Error processing report: ' + error.message);
        } finally {
            loader.style.display = 'none';
        }
    });

    // Chat functionality
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendMessage');
    const chatMessages = document.getElementById('chatMessages');
    const roleSelect = document.getElementById('roleSelect');

    // Add keypress event for message input
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Add click event for send button
    sendButton.addEventListener('click', sendMessage);

    async function sendMessage() {
        const message = messageInput.value.trim();
        if (!message || !currentReport) {
            if (!currentReport) {
                alert('Please upload a report first before starting the chat.');
            }
            return;
        }

        const role = roleSelect.value;

        messageInput.disabled = true;
        sendButton.disabled = true;

        appendMessage('You', message);
        messageInput.value = '';

        const typingIndicator = appendTypingIndicator();

        try {
            console.log('Sending request with:', {
                message,
                role,
                report: currentReport,
                session_id: sessionId
            });

            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({
                    message,
                    role,
                    report: currentReport,
                    session_id: sessionId
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Received response:', data);
            
            typingIndicator.remove();

            if (data.error) {
                throw new Error(data.error);
            }

            appendMessage('Assistant', data.response);
            
        } catch (error) {
            console.error('Chat error:', error);
            typingIndicator.remove();
            appendMessage('System', `Error: ${error.message}. Please try again.`);
        } finally {
            messageInput.disabled = false;
            sendButton.disabled = false;
            messageInput.focus();
        }
    }

    function appendMessage(sender, message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message message-${sender.toLowerCase()}`;
        
        // Create the header with sender and timestamp
        const headerDiv = document.createElement('div');
        headerDiv.className = 'message-header';
        headerDiv.innerHTML = `
            <strong>${sender}</strong>
            <span class="message-time">${new Date().toLocaleTimeString()}</span>
        `;
        
        // Create the content div and render markdown if it's from the Assistant
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (sender === 'Assistant') {
            // Sanitize and render markdown
            contentDiv.innerHTML = marked.parse(message, {
                breaks: true,
                sanitize: true
            });
        } else {
            // For user messages, just escape HTML and preserve line breaks
            contentDiv.textContent = message;
        }
        
        // Assemble the message
        messageDiv.appendChild(headerDiv);
        messageDiv.appendChild(contentDiv);
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function appendTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message message-typing';
        typingDiv.innerHTML = `
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        chatMessages.appendChild(typingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return typingDiv;
    }

    function displayResults(data) {
        // Display report details with tables and download button
        const reportContent = document.getElementById('reportContent');
        reportContent.innerHTML = `
            <div class="report-actions">
                <button id="downloadReportBtn" class="download-btn">
                    Download Report (JSON)
                </button>
            </div>
            <div class="info-tables-container">
                <div class="info-table">
                    <h3>Patient Information</h3>
                    <table class="results-table">
                        <tbody>
                            ${generatePatientInfoRows(data.report.patient_info)}
                        </tbody>
                    </table>
                </div>
                <div class="info-table">
                    <h3>Laboratory Information</h3>
                    <table class="results-table">
                        <tbody>
                            ${generateLabInfoRows(data.report.lab_info, data.report.test_name)}
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="lab-results-table">
                <h3>Test Results</h3>
                <div class="table-container">
                    <table class="results-table">
                        <thead>
                            <tr>
                                <th>Parameter</th>
                                <th>Value</th>
                                <th>Reference Range</th>
                                <th>Unit</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${generateTableRows(data.report.lab_results)}
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        // Add helper functions for generating table rows
        function generatePatientInfoRows(patientInfo) {
            return Object.entries(patientInfo)
                .map(([key, value]) => `
                    <tr>
                        <th>${formatKey(key)}</th>
                        <td>${value || 'N/A'}</td>
                    </tr>
                `).join('');
        }

        function generateLabInfoRows(labInfo, testName) {
            let rows = `
                <tr>
                    <th>Test Name</th>
                    <td>${testName || 'N/A'}</td>
                </tr>
            `;
            
            rows += Object.entries(labInfo)
                .map(([key, value]) => {
                    if (typeof value === 'object') {
                        // Handle nested objects like lab_contact
                        return Object.entries(value)
                            .map(([subKey, subValue]) => `
                                <tr>
                                    <th>${formatKey(key + '_' + subKey)}</th>
                                    <td>${subValue || 'N/A'}</td>
                                </tr>
                            `).join('');
                    }
                    return `
                        <tr>
                            <th>${formatKey(key)}</th>
                            <td>${value || 'N/A'}</td>
                        </tr>
                    `;
                }).join('');
            return rows;
        }

        function formatKey(key) {
            return key.split('_')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
        }

        // Add event listener for download button
        document.getElementById('downloadReportBtn').addEventListener('click', () => {
            downloadReport(data.report);
        });
        
        // Modify the plots display
        const plotsContent = document.getElementById('plotsContent');
        plotsContent.innerHTML = ''; // Clear existing plots
        
        // Create a container for plots
        const plotsContainer = document.createElement('div');
        plotsContainer.className = 'plots-container-vertical';
        
        // Display plots from the static/plots directory
        if (data.report.lab_results) {
            Object.keys(data.report.lab_results).forEach(param => {
                const details = data.report.lab_results[param];
                if (details.status !== 'Normal') {
                    const plotCard = document.createElement('div');
                    plotCard.className = 'plot-card-vertical';
                    
                    const plotImg = document.createElement('img');
                    plotImg.src = `/static/plots/${param.replace(/\s+/g, '_')}.png`;
                    plotImg.alt = `${param} Plot`;
                    plotImg.className = 'result-plot';
                    
                    // Add load error handling
                    plotImg.onerror = function() {
                        this.parentElement.innerHTML = `
                            <div class="plot-error">
                                <p>Plot not available for ${param}</p>
                            </div>
                        `;
                    };
                    
                    const plotTitle = document.createElement('h4');
                    plotTitle.textContent = param;
                    
                    plotCard.appendChild(plotTitle);
                    plotCard.appendChild(plotImg);
                    plotsContainer.appendChild(plotCard);
                }
            });
        }
        
        plotsContent.appendChild(plotsContainer);
        
        // Display insights
        const insightsContent = document.getElementById('insightsContent');
        if (data.insights && data.insights.abnormal_parameters) {
            insightsContent.innerHTML = formatInsights(data.insights);
        }
    }

    function generateTableRows(labResults) {
        return Object.entries(labResults)
            .map(([param, details]) => `
                <tr class="status-${details.status.toLowerCase()}">
                    <td>${param}</td>
                    <td>${details.value}</td>
                    <td>${details.reference_range}</td>
                    <td>${details.unit}</td>
                    <td>${details.status}</td>
                </tr>
            `).join('');
    }

    function formatInsights(insights) {
        return `
            <div class="insights-container">
                ${insights.abnormal_parameters.map(param => `
                    <div class="insight-card">
                        <h3>${param.parameter} (${param.status})</h3>
                        <div class="insight-section">
                            <h4>Possible Health Effects:</h4>
                            <ul>
                                ${param.possible_disease.map(disease => `<li>${disease}</li>`).join('')}
                            </ul>
                        </div>
                        <div class="insight-section">
                            <h4>Possible Causes:</h4>
                            <ul>
                                ${param.possible_causes.map(cause => `<li>${cause}</li>`).join('')}
                            </ul>
                        </div>
                        <div class="insight-section">
                            <h4>Dietary Suggestions:</h4>
                            <ul>
                                ${param.dietary_suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}
                            </ul>
                        </div>
                        <div class="insight-section">
                            <h4>Lifestyle Changes:</h4>
                            <ul>
                                ${param.lifestyle_changes.map(change => `<li>${change}</li>`).join('')}
                            </ul>
                        </div>
                        <div class="insight-section">
                            <h4>Medical Advice:</h4>
                            <p>${param.medical_advice}</p>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    function downloadReport(report) {
        const dataStr = JSON.stringify(report, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const downloadLink = document.createElement('a');
        downloadLink.href = url;
        downloadLink.download = 'blood_report.json';
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
        URL.revokeObjectURL(url);
    }
}); 