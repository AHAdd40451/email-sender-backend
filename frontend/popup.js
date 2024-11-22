// const API_BASE_URL = 'http://localhost:5000';
const API_BASE_URL = 'https://email-sender-backend-dyxz.onrender.com';

document.addEventListener('DOMContentLoaded', initializeApp);

async function initializeApp() {
    console.log('Initializing app...');

    try {
        // Check authentication
        const token = localStorage.getItem('token');
        if (!token) {
            console.log('No token found, redirecting to login');
            window.location.href = 'login.html';
            return;
        }

        // Setup event listeners first
        setupEventListeners();
        
        // Load initial data
        await loadSmtpSettings();
        
        await loadLogs();
        
        await loadSavedData();
        
        console.log('App initialized successfully');
        addLogEntry('Application initialized successfully', 'success');
    } catch (error) {
        console.error('Error initializing app:', error);
        addLogEntry(`Error initializing application: ${error.message}`, 'error');
    }
}

function setupEventListeners() {
    // Tab Switching
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');
            switchTab(tabId);
        });
    });

    // SMTP Form
    const smtpForm = document.getElementById('smtp-form');
    if (smtpForm) {
        smtpForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await saveSmtpSettings();
        });
    }

    // Email Management
    const addEmailBtn = document.getElementById('add-email-btn');
    if (addEmailBtn) {
        addEmailBtn.addEventListener('click', addEmail);
    }

    const newEmailInput = document.getElementById('new-email');
    if (newEmailInput) {
        newEmailInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                addEmail();
            }
        });
    }

    // Send Button
    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) {
        sendBtn.addEventListener('click', sendEmails);
    }

    // Logout Button
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            localStorage.removeItem('token');
            window.location.href = 'login.html';
        });
    }

    // Clear Logs Button
    const clearLogsBtn = document.getElementById('clear-logs-btn');
    if (clearLogsBtn) {
        clearLogsBtn.addEventListener('click', clearLogs);
    }

    // Auto-save email template
    const emailSubject = document.getElementById('email-subject');
    const emailBody = document.getElementById('email-body');
    
    if (emailSubject) {
        emailSubject.addEventListener('input', debounce(saveEmailTemplate, 1000));
    }
    
    if (emailBody) {
        emailBody.addEventListener('input', debounce(saveEmailTemplate, 1000));
    }
    
    // Auto-save email list
    const emailList = document.getElementById('email-list');
    if (emailList) {
        emailList.addEventListener('input', debounce(saveEmailList, 1000));
    }

    // CSV Import
    const importCsvBtn = document.getElementById('import-csv-btn');
    const csvFileInput = document.getElementById('csv-file');

    if (importCsvBtn && csvFileInput) {
        importCsvBtn.addEventListener('click', () => {
            csvFileInput.click();
        });

        csvFileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
                    handleCsvImport(file);
                } else {
                    addLogEntry('Please select a valid CSV file', 'error');
                }
                // Reset file input
                csvFileInput.value = '';
            }
        });
    }

    document.getElementById('attachments').addEventListener('change', function(e) {
        const attachmentList = document.getElementById('attachment-list');
        attachmentList.innerHTML = '';
        
        for (const file of this.files) {
            const item = document.createElement('div');
            item.className = 'attachment-item';
            
            const name = document.createElement('span');
            name.textContent = `${file.name} (${formatFileSize(file.size)})`;
            
            const removeBtn = document.createElement('button');
            removeBtn.textContent = '×';
            removeBtn.onclick = () => {
                // Remove file from input
                const dt = new DataTransfer();
                const files = [...this.files];
                const index = files.indexOf(file);
                files.splice(index, 1);
                files.forEach(f => dt.items.add(f));
                this.files = dt.files;
                item.remove();
            };
            
            item.appendChild(name);
            item.appendChild(removeBtn);
            attachmentList.appendChild(item);
        }
    });

    document.getElementById('attachments').addEventListener('change', async function(e) {
        const attachmentList = document.getElementById('attachment-list');
        attachmentList.innerHTML = '';
        
        // Save the template with new attachments
        await saveEmailTemplate();
        
        // Reload the attachment list
        await loadSavedData();
    });

    // Clear Emails Button
    const clearEmailsBtn = document.getElementById('clear-emails-btn');
    if (clearEmailsBtn) {
        clearEmailsBtn.addEventListener('click', async () => {
            const emailList = document.getElementById('email-list');
            emailList.value = '';
            await saveEmailList(); // Save the empty list
            addLogEntry('Email list cleared', 'info');
        });
    }
}

function switchTab(tabId) {
    // Update active tab button
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
    });

    // Update active content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === tabId);
    });
}

async function loadInitialData() {
    await loadSmtpSettings();
    addLogEntry('Settings loaded', 'info');
}

function addEmail() {
    const emailInput = document.getElementById('new-email');
    const emailList = document.getElementById('email-list');
    
    const email = emailInput.value.trim();
    if (isValidEmail(email)) {
        const emails = new Set(emailList.value.split('\n').filter(e => e.trim()));
        if (!emails.has(email)) {
            emails.add(email);
            emailList.value = Array.from(emails).join('\n');
            emailInput.value = '';
            addLogEntry(`Added email: ${email}`, 'success');
        } else {
            addLogEntry('Email already exists in the list', 'warning');
        }
    } else {
        addLogEntry('Please enter a valid email address', 'error');
    }
}

async function saveSmtpSettings() {
    try {
        const settings = {
            smtp_server: document.getElementById('smtp-server').value,
            smtp_port: parseInt(document.getElementById('smtp-port').value),
            username: document.getElementById('username').value,
            password: document.getElementById('password').value,
            sender_name: document.getElementById('sender-name').value,
            delay: parseInt(document.getElementById('delay').value) || 5
        };

        // Validate settings
        if (!settings.smtp_server || !settings.smtp_port || !settings.username || !settings.password) {
            addLogEntry('All SMTP fields are required', 'error');
            return;
        }

        console.log('Saving settings:', settings); // Debug log

        const response = await fetch(`${API_BASE_URL}/smtp-settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify(settings)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'Failed to save settings');
        }

        const data = await response.json();
        addLogEntry('SMTP settings saved successfully', 'success');
        return data;

    } catch (error) {
        console.error('Error saving settings:', error);
        addLogEntry(`Failed to save settings: ${error.message}`, 'error');
        throw error;
    }
}

async function loadSmtpSettings() {
    try {
        console.log('Loading SMTP settings...'); // Debug log

        const response = await fetch(`${API_BASE_URL}/smtp-settings`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });

        // Log the response for debugging
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            if (response.status === 401) {
                // Handle unauthorized access
                localStorage.removeItem('token');
                window.location.href = 'login.html';
                return;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('Received non-JSON response from server');
        }

        const data = await response.json();
        console.log('Received settings:', data); // Debug log

        if (data.settings) {
            document.getElementById('smtp-server').value = data.settings.smtp_server || '';
            document.getElementById('smtp-port').value = data.settings.smtp_port || '';
            document.getElementById('username').value = data.settings.username || '';
            document.getElementById('password').value = data.settings.password || '';
            document.getElementById('sender-name').value = data.settings.sender_name || '';
            document.getElementById('delay').value = data.settings.delay || 5;
            addLogEntry('Settings loaded successfully', 'success');
        } else {
            addLogEntry('No existing settings found', 'info');
        }
    } catch (error) {
        console.error('Error loading settings:', error);
        addLogEntry(`Failed to load settings: ${error.message}`, 'error');
    }
}

async function sendEmails() {
    try {
        // First check if SMTP settings exist
        const smtpServer = document.getElementById('smtp-server').value;
        if (!smtpServer) {
            addLogEntry('Please configure SMTP settings first', 'error');
            switchTab('settings');
            return;
        }

        const emailList = document.getElementById('email-list').value
            .split('\n')
            .map(email => email.trim())
            .filter(email => email && isValidEmail(email));

        if (emailList.length === 0) {
            addLogEntry('No valid email addresses provided', 'error');
            return;
        }

        const subject = document.getElementById('email-subject').value;
        if (!subject) {
            addLogEntry('Email subject is required', 'error');
            return;
        }

        const body = document.getElementById('email-body').value;
        if (!body) {
            addLogEntry('Email body is required', 'error');
            return;
        }

        // Handle attachments
        const attachmentInput = document.getElementById('attachments');
        const attachments = [];
        
        for (const file of attachmentInput.files) {
            const reader = new FileReader();
            const attachment = await new Promise((resolve, reject) => {
                reader.onload = () => {
                    resolve({
                        filename: file.name,
                        content: reader.result.split(',')[1], // Get base64 content
                        contentType: file.type
                    });
                };
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
            attachments.push(attachment);
        }

        addLogEntry('Starting email send process...', 'info');
        addLogEntry(`Preparing to send to ${emailList.length} recipients...`, 'info');

        const emailData = {
            emails: emailList,
            subject: subject,
            body: body,
            attachments: attachments
        };

        const response = await fetch(`${API_BASE_URL}/send-emails`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify(emailData)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || 'Failed to send emails');
        }

        // Show success message
        addLogEntry(data.message, 'success');

        // Show detailed results if available
        if (data.details) {
            if (data.details.successful > 0) {
                addLogEntry(`Successfully sent: ${data.details.successful}`, 'success');
            }
            if (data.details.failed > 0) {
                addLogEntry(`Failed to send: ${data.details.failed}`, 'error');
            }
            // Show individual errors if any
            if (data.details.errors && data.details.errors.length > 0) {
                data.details.errors.forEach(error => {
                    addLogEntry(error, 'error');
                });
            }
        }

    } catch (error) {
        console.error('Error sending emails:', error);
        addLogEntry(`Failed to send emails: ${error.message}`, 'error');
    }
}

// Add this helper function to validate emails
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// Add this helper function to check SMTP settings before sending
async function checkSmtpSettings() {
    const requiredFields = ['smtp-server', 'smtp-port', 'username', 'password'];
    for (const field of requiredFields) {
        const value = document.getElementById(field).value;
        if (!value) {
            addLogEntry(`SMTP ${field.replace('-', ' ')} is required`, 'error');
            switchTab('settings');
            return false;
        }
    }
    return true;
}

function addLogEntry(message, type = 'info') {
    const logEntries = document.getElementById('log-entries');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const timestamp = new Date().toLocaleTimeString();
    entry.textContent = `[${timestamp}] ${message}`;
    logEntries.appendChild(entry);
    logEntries.scrollTop = logEntries.scrollHeight;
}

async function loadLogs() {
    try {
        const token = localStorage.getItem('token');
        if (!token) {
            throw new Error('No authentication token found');
        }

        const response = await fetch(`${API_BASE_URL}/logs`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.status === 401) {
            localStorage.removeItem('token');
            window.location.href = 'login.html';
            return;
        }

        const data = await response.json();
        
        if (data.status === 'error') {
            throw new Error(data.message);
        }

        const logEntries = document.getElementById('log-entries');
        logEntries.innerHTML = '';

        if (data.logs && Array.isArray(data.logs)) {
            // Sort logs by timestamp in descending order
            const sortedLogs = data.logs.sort((a, b) => 
                new Date(b.timestamp) - new Date(a.timestamp)
            );

            sortedLogs.forEach(log => {
                const entry = document.createElement('div');
                entry.className = `log-entry ${log.level}`;
                
                // Format timestamp
                const timestamp = new Date(log.timestamp).toLocaleString();
                
                // Create log message with proper formatting
                entry.innerHTML = `
                    <span class="log-timestamp">[${timestamp}]</span>
                    <span class="log-level ${log.level}">${log.level.toUpperCase()}</span>
                    <span class="log-message">${log.message}</span>
                `;
                
                // Add details if they exist
                if (log.details) {
                    const detailsSpan = document.createElement('span');
                    detailsSpan.className = 'log-details';
                    detailsSpan.textContent = JSON.stringify(log.details);
                    entry.appendChild(detailsSpan);
                }
                
                logEntries.appendChild(entry);
            });

            // Add log count
            const logCount = document.createElement('div');
            logCount.className = 'log-count';
            logCount.textContent = `Showing ${sortedLogs.length} logs`;
            logEntries.insertBefore(logCount, logEntries.firstChild);
        }

    } catch (error) {
        console.error('Error loading logs:', error);
        addLogEntry(`Failed to load logs: ${error.message}`, 'error');
    }
}

async function clearLogs() {
    try {
        const response = await fetch(`${API_BASE_URL}/logs/clear`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });

        if (!response.ok) {
            throw new Error('Failed to clear logs');
        }

        const data = await response.json();
        addLogEntry(data.message, 'success');
        await loadLogs(); // Reload logs after clearing

    } catch (error) {
        console.error('Error clearing logs:', error);
        addLogEntry('Failed to clear logs', 'error');
    }
}

async function loadSavedData() {
    try {
        const result = await chrome.storage.local.get(['emailTemplate', 'emailList']);
        
        // Load email template
        if (result.emailTemplate) {
            document.getElementById('email-subject').value = result.emailTemplate.subject || '';
            document.getElementById('email-body').value = result.emailTemplate.body || '';
            
            // Load attachments
            if (result.emailTemplate.attachments) {
                const attachmentList = document.getElementById('attachment-list');
                attachmentList.innerHTML = '';
                
                result.emailTemplate.attachments.forEach(attachment => {
                    const item = document.createElement('div');
                    item.className = 'attachment-item';
                    
                    const name = document.createElement('span');
                    name.textContent = `${attachment.filename} (${formatFileSize(attachment.size)})`;
                    
                    const removeBtn = document.createElement('button');
                    removeBtn.textContent = '×';
                    removeBtn.onclick = async () => {
                        item.remove();
                        // Remove attachment from storage
                        const template = result.emailTemplate;
                        template.attachments = template.attachments.filter(
                            a => a.filename !== attachment.filename
                        );
                        await chrome.storage.local.set({ emailTemplate: template });
                    };
                    
                    item.appendChild(name);
                    item.appendChild(removeBtn);
                    attachmentList.appendChild(item);
                });
            }
        }
        
        // Load email list
        if (result.emailList) {
            document.getElementById('email-list').value = result.emailList.join('\n');
        }
        
    } catch (error) {
        console.error('Error loading saved data:', error);
        addLogEntry('Failed to load saved data', 'error');
    }
}

// Function to save template
async function saveEmailTemplate() {
    try {
        const subject = document.getElementById('email-subject').value;
        const body = document.getElementById('email-body').value;
        const attachmentInput = document.getElementById('attachments');
        const attachments = [];
        
        for (const file of attachmentInput.files) {
            const reader = new FileReader();
            const attachment = await new Promise((resolve, reject) => {
                reader.onload = () => {
                    resolve({
                        filename: file.name,
                        content: reader.result.split(',')[1],
                        contentType: file.type,
                        size: file.size
                    });
                };
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
            attachments.push(attachment);
        }
        
        await chrome.storage.local.set({
            emailTemplate: {
                subject: subject,
                body: body,
                attachments: attachments
            }
        });
        
        addLogEntry('Email template saved with attachments', 'success');
    } catch (error) {
        console.error('Error saving template:', error);
        addLogEntry('Failed to save template', 'error');
    }
}

// Function to save email list
async function saveEmailList() {
    try {
        const emailListText = document.getElementById('email-list').value;
        const emailList = emailListText.split('\n').filter(email => email.trim());
        
        await chrome.storage.local.set({
            emailList: emailList
        });
        
        addLogEntry('Email list saved', 'success');
    } catch (error) {
        console.error('Error saving email list:', error);
        addLogEntry('Failed to save email list', 'error');
    }
}

// Add debounce utility function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Add this function after the addEmail function
async function handleCsvImport(file) {
    try {
        const reader = new FileReader();
        
        reader.onload = async (event) => {
            const csvContent = event.target.result;
            const lines = csvContent.split(/\r\n|\n/);
            const emailList = document.getElementById('email-list');
            const currentEmails = new Set(emailList.value.split('\n').filter(e => e.trim()));
            let importCount = 0;
            let invalidCount = 0;
            let duplicateCount = 0;

            for (let line of lines) {
                const email = line.trim();
                if (email && isValidEmail(email)) {
                    if (!currentEmails.has(email)) {
                        currentEmails.add(email);
                        importCount++;
                    } else {
                        duplicateCount++;
                    }
                } else if (email) {
                    invalidCount++;
                }
            }

            emailList.value = Array.from(currentEmails).join('\n');
            
            // Save the updated email list
            await saveEmailList();

            // Show import results
            addLogEntry(`CSV Import Results:`, 'info');
            addLogEntry(`- ${importCount} emails imported successfully`, 'success');
            if (duplicateCount > 0) {
                addLogEntry(`- ${duplicateCount} duplicate emails skipped`, 'warning');
            }
            if (invalidCount > 0) {
                addLogEntry(`- ${invalidCount} invalid emails skipped`, 'error');
            }
        };

        reader.onerror = () => {
            throw new Error('Error reading CSV file');
        };

        reader.readAsText(file);
    } catch (error) {
        console.error('Error importing CSV:', error);
        addLogEntry(`Failed to import CSV: ${error.message}`, 'error');
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}