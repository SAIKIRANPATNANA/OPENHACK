document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('uploadForm');
    const loader = document.getElementById('loader');
    const resultsSection = document.querySelector('.results-section');
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const messageInput = document.getElementById('messageInput');
    const sendMessageBtn = document.getElementById('sendMessage');
    const chatMessages = document.getElementById('chatMessages');
    const roleSelect = document.getElementById('roleSelect');

    let currentReport = null;
    let sessionId = generateSessionId();
    let chatHistory = [];  // Store chat history

    // Tab switching functionality
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.getAttribute('data-tab');
            
            // Remove active class from all buttons and contents
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            // Add active class to clicked button and corresponding content
            btn.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });

    // File upload handling
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('reportFile');
        const file = fileInput.files[0];

        if (!file) {
            alert('Please select a file first.');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            loader.style.display = 'block';
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            if (data.error) {
                throw new Error(data.error);
            }

            currentReport = data.report;
            displayResults(data);
            resultsSection.style.display = 'block';
            
            // Reset chat history when new report is uploaded
            chatHistory = [];
            chatMessages.innerHTML = '';

        } catch (error) {
            alert(`Error: ${error.message}`);
        } finally {
            loader.style.display = 'none';
        }
    });

    // Chat functionality
    sendMessageBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    async function sendMessage() {
        const message = messageInput.value.trim();
        if (!message || !currentReport) return;

        const role = roleSelect.value;
        
        // Add user message to chat
        appendMessage('You', message);
        messageInput.value = '';

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
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
            if (data.error) {
                throw new Error(data.error);
            }

            // Add bot's response to chat
            appendMessage('Assistant', data.response);

        } catch (error) {
            appendMessage('System', `Error: ${error.message}`);
        }
    }

    function appendMessage({ sender, content, timestamp }) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message message-${sender.toLowerCase()}`;
        
        const formattedContent = marked.parse(content); // Use marked to parse markdown
        
        messageDiv.innerHTML = `
            <div class="message-header">
                <strong>${sender}</strong>
                <span class="message-time">${new Date().toLocaleTimeString()}</span>
            </div>
            <div class="message-content">${formattedContent}</div>
        `;
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function formatMessage(content) {
        try {
            return marked.parse(content);
        } catch (error) {
            console.error('Error parsing markdown:', error);
            return content;
        }
    }

    function generateSessionId() {
        return 'session_' + Math.random().toString(36).substr(2, 9);
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
            <div class="report-tables">
                <div class="table-section">
                    <h3>Patient Information</h3>
                    <div class="table-container">
                        <table class="results-table">
                            <tbody>
                                ${generatePatientInfoRows(data.report.patient_info)}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="table-section">
                    <h3>Laboratory Information</h3>
                    <div class="table-container">
                        <table class="results-table">
                            <tbody>
                                <tr>
                                    <td><strong>Test Name</strong></td>
                                    <td>${data.report.test_name || 'N/A'}</td>
                                </tr>
                                ${generateLabInfoRows(data.report.lab_info)}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="table-section">
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
            </div>
        `;

        // Display plots
        const plotsContent = document.getElementById('plotsContent');
        plotsContent.innerHTML = `
            <div class="plots-container">
                ${generatePlots()}
            </div>
        `;

        // Display insights
        if (data.insights && data.insights.abnormal_parameters) {
            displayInsights(data.insights);
        }

        // Add event listener for download button
        document.getElementById('downloadReportBtn').addEventListener('click', () => {
            downloadReport(data.report);
        });
    }

    function generatePatientInfoRows(patientInfo) {
        return Object.entries(patientInfo)
            .map(([key, value]) => `
                <tr>
                    <td><strong>${formatLabel(key)}</strong></td>
                    <td>${value || 'N/A'}</td>
                </tr>
            `).join('');
    }

    function generateLabInfoRows(labInfo) {
        return Object.entries(labInfo)
            .map(([key, value]) => {
                // Handle nested objects like lab_contact
                if (typeof value === 'object' && value !== null) {
                    return Object.entries(value)
                        .map(([subKey, subValue]) => `
                            <tr>
                                <td><strong>${formatLabel(subKey)}</strong></td>
                                <td>${subValue || 'N/A'}</td>
                            </tr>
                        `).join('');
                }
                return `
                    <tr>
                        <td><strong>${formatLabel(key)}</strong></td>
                        <td>${value || 'N/A'}</td>
                    </tr>
                `;
            }).join('');
    }

    function generateTableRows(results) {
        return Object.entries(results).map(([param, details]) => `
            <tr class="status-${details.status.toLowerCase()}">
                <td>${param}</td>
                <td>${details.value}</td>
                <td>${details.reference_range}</td>
                <td>${details.unit}</td>
                <td>${details.status}</td>
            </tr>
        `).join('');
    }

    function generatePlots() {
        if (!currentReport || !currentReport.lab_results) return '';

        const abnormalParams = Object.entries(currentReport.lab_results)
            .filter(([_, details]) => details.status !== 'Normal')
            .map(([param, details]) => ({
                name: param,
                status: details.status
            }));

        if (abnormalParams.length === 0) {
            return '<div class="plot-error">No abnormal parameters to display</div>';
        }

        return abnormalParams.map(param => {
            const safeName = param.name.replace(/\s+/g, '_').toLowerCase();
            return `
                <div class="plot-card">
                    <h4>${param.name} (${param.status})</h4>
                    <img src="/static/plots/${safeName}.png" 
                         alt="${param.name} Plot" 
                         class="result-plot"
                         onerror="this.onerror=null; this.src='/static/images/plot-error.png';">
                </div>
            `;
        }).join('');
    }

    function displayInsights(insights) {
        const insightsContent = document.getElementById('insightsContent');
        insightsContent.innerHTML = `
            <div class="insights-container">
                ${insights.abnormal_parameters.map(param => `
                    <div class="insight-card">
                        <h3>${param.parameter} (${param.status})</h3>
                        
                        <div class="insight-section">
                            <h4>Possible Health Effects</h4>
                            <ul>
                                ${param.possible_disease.map(disease => `<li>${disease}</li>`).join('')}
                            </ul>
                        </div>

                        <div class="insight-section">
                            <h4>Possible Causes</h4>
                            <ul>
                                ${param.possible_causes.map(cause => `<li>${cause}</li>`).join('')}
                            </ul>
                        </div>

                        <div class="insight-section">
                            <h4>Dietary Suggestions</h4>
                            <ul>
                                ${param.dietary_suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}
                            </ul>
                        </div>

                        <div class="insight-section">
                            <h4>Lifestyle Changes</h4>
                            <ul>
                                ${param.lifestyle_changes.map(change => `<li>${change}</li>`).join('')}
                            </ul>
                        </div>

                        <div class="insight-section">
                            <h4>Medical Advice</h4>
                            <p>${param.medical_advice}</p>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    function formatLabel(key) {
        // Convert snake_case to Title Case
        return key.split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }

    function downloadReport(report) {
        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(report, null, 2));
        const downloadAnchorNode = document.createElement('a');
        downloadAnchorNode.setAttribute("href", dataStr);
        downloadAnchorNode.setAttribute("download", "blood_report.json");
        document.body.appendChild(downloadAnchorNode);
        downloadAnchorNode.click();
        downloadAnchorNode.remove();
    }
}); 