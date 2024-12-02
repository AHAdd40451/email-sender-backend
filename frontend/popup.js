import config from './config.js';
const { API_BASE_URL } = config;

// Add this after your other imports
let socket;

function initializeSocket(userId) {
    try {
        socket = io(API_BASE_URL, {
            transports: ['websocket'],
            upgrade: false,
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000
        });
        
        socket.on('connect', () => {
            console.log('Connected to WebSocket');
            // Join user-specific room when connected
            socket.emit('join', { userId: userId });
        });

        // Listen for real-time logs
        socket.on('log_update', (logEntry) => {
            console.log('Received real-time log:', logEntry);
            addLogEntryToUI(logEntry, true); // true indicates this is a real-time entry
        });

        socket.on('logs_message', (data) => {
            console.log('Logs message:', data.message);
        });

        socket.on('disconnect', () => {
            console.log('Disconnected from WebSocket');
        });

        socket.on('connect_error', (error) => {
            console.error('Socket connection error:', error);
        });

    } catch (error) {
        console.error('Error initializing app:', error);
        addLogEntryToUI({
            level: 'error',
            message: `Initialization error: ${error.message}`,
            timestamp: new Date().toISOString()
        });
    }
}

function addLogEntryToUI(logEntry, isRealtime = false) {
    const logEntries = document.getElementById('log-entries');
    const entry = document.createElement('div');
    entry.className = `log-entry ${logEntry.level}`;
    
    if (isRealtime) {
        entry.classList.add('realtime-log');
        entry.style.animation = 'fadeIn 0.5s ease-in';
    }
    
    // Format the timestamp
    const timestamp = new Date(logEntry.timestamp).toLocaleString();
    
    // Only show details if they contain information other than user_id
    const hasRelevantDetails = logEntry.details && 
        Object.keys(logEntry.details).length > 0 && 
        !(Object.keys(logEntry.details).length === 1 && logEntry.details.user_id);

    entry.innerHTML = `
        <span class="log-timestamp">[${timestamp}]</span>
        <span class="log-level ${logEntry.level}">${logEntry.level.toUpperCase()}</span>
        <span class="log-message">${logEntry.message}</span>
        ${hasRelevantDetails ? `
            <span class="log-details">${formatDetails(logEntry.details)}</span>
        ` : ''}
    `;
    
    // Insert at the top for real-time logs
    logEntries.insertBefore(entry, logEntries.firstChild);
    
    // Limit the number of displayed logs
    const maxDisplayedLogs = 100;
    while (logEntries.children.length > maxDisplayedLogs) {
        logEntries.removeChild(logEntries.lastChild);
    }
}

// Helper function to format details
function formatDetails(details) {
    if (!details) return '';
    
    // Filter out user_id and empty objects
    const relevantDetails = Object.entries(details)
        .filter(([key, value]) => key !== 'user_id' && value !== undefined && value !== null)
        .reduce((obj, [key, value]) => {
            obj[key] = value;
            return obj;
        }, {});
    
    if (Object.keys(relevantDetails).length === 0) return '';
    
    return JSON.stringify(relevantDetails, null, 2);
}

document.addEventListener('DOMContentLoaded', initializeApp);



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
                    console.error('Please select a valid CSV file');
                }
                // Reset file input
                csvFileInput.value = '';
            }
        });
    }

    document.getElementById('attachments').addEventListener('change', function (e) {
        const attachmentList = document.getElementById('attachment-list');
        attachmentList.innerHTML = '';

        for (const file of this.files) {
            const item = document.createElement('div');
            item.className = 'attachment-item';

            const name = document.createElement('span');
            name.textContent = `${file.name} (${formatFileSize(file.size)})`;

            const removeBtn = document.createElement('button');
            removeBtn.textContent = '';
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


    // Clear Emails Button
    const clearEmailsBtn = document.getElementById('clear-emails-btn');
    if (clearEmailsBtn) {
        clearEmailsBtn.addEventListener('click', async () => {
            const emailList = document.getElementById('email-list');
            emailList.value = '';
            await saveEmailList(); // Save the empty list
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

async function addEmail() {
    const emailInput = document.getElementById('new-email');
    const emailList = document.getElementById('email-list');

    const email = emailInput.value.trim();
    if (isValidEmail(email)) {
        const emails = new Set(emailList.value.split('\n').filter(e => e.trim()));
        if (!emails.has(email)) {
            emails.add(email);
            emailList.value = Array.from(emails).join('\n');
            emailInput.value = '';
            
            // Save to both backend and local storage
            await saveEmailList();
            await saveEmailTemplate(); // Save any template changes too
        } else {
            console.error('Email already exists in the list');
        }
    } else {
        console.error('Please enter a valid email address');
    }
}

async function saveSmtpSettings() {
    try {
        const response = await fetch(`${API_BASE_URL}/smtp-settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({
                smtp_server: document.getElementById('smtp-server').value,
                smtp_port: document.getElementById('smtp-port').value,
                username: document.getElementById('username').value,
                password: document.getElementById('password').value,
                sender_name: document.getElementById('sender-name').value,
                delay: document.getElementById('delay').value
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.message || 'Failed to save settings');
        }

    } catch (error) {
        console.error('Error saving SMTP settings:', error);
    }
}

async function loadSmtpSettings() {
    try {
        const response = await fetch(`${API_BASE_URL}/smtp-settings`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('Received non-JSON response from server');
        }

        const data = await response.json();

        if (data.settings) {
            document.getElementById('smtp-server').value = data.settings.smtp_server || '';
            document.getElementById('smtp-port').value = data.settings.smtp_port || '';
            document.getElementById('username').value = data.settings.username || '';
            document.getElementById('password').value = data.settings.password || '';
            document.getElementById('sender-name').value = data.settings.sender_name || '';
            document.getElementById('delay').value = data.settings.delay || 5;
        }
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

async function sendEmails() {
    const sendBtn = document.getElementById('send-btn');
    const originalBtnText = sendBtn.textContent;
    
    try {
        // Prevent multiple sends
        if (sendBtn.disabled) {
            return;
        }

        // First check if SMTP settings exist
        const smtpServer = document.getElementById('smtp-server').value;
        if (!smtpServer) {
            addLogEntryToUI({
                level: 'error',
                message: 'Please configure SMTP settings first',
                timestamp: new Date().toISOString()
            });
            switchTab('settings');
            return;
        }

        // Update button to show loading state
        sendBtn.disabled = true;
        sendBtn.innerHTML = `
            <span class="spinner"></span>
            Sending... <button class="cancel-btn">Cancel</button>
        `;

        // Get email list and validate
        const emailList = document.getElementById('email-list').value
            .split('\n')
            .map(email => email.trim())
            .filter(email => email && isValidEmail(email));

        if (emailList.length === 0) {
            throw new Error('No valid email addresses provided');
        }

        // Get subject and body
        const subject = document.getElementById('email-subject').value;
        const body = document.getElementById('email-body').value;

        if (!subject || !body) {
            throw new Error('Email subject and body are required');
        }

        // Handle attachments
        const attachmentInput = document.getElementById('attachments');
        const attachments = [];
        if (attachmentInput && attachmentInput.files.length > 0) {
            for (const file of attachmentInput.files) {
                const attachment = await readFileAsBase64(file);
                attachments.push(attachment);
            }
        }

        // Update button to show loading state
        sendBtn.disabled = true;
        sendBtn.innerHTML = `
            <span class="spinner"></span>
            Sending... <button class="cancel-btn">Cancel</button>
        `;

        // Add cancel button functionality
        const cancelBtn = sendBtn.querySelector('.cancel-btn');
        if (cancelBtn) {
            cancelBtn.onclick = (e) => {
                e.stopPropagation();
                chrome.runtime.sendMessage({ action: 'cancelSending' });
            };
        }

        // Send message to background script
        chrome.runtime.sendMessage({
            action: 'sendEmails',
            data: {
                emails: emailList,
                subject,
                body,
                attachments,
                token: localStorage.getItem('token')
            }
        });

        // Listen for status updates
        chrome.runtime.onMessage.addListener(function(message) {
            if (message.action === 'statusUpdate') {
                updateUIStatus(message.status);
            }
        });

    } catch (error) {
        console.error('Error preparing email send:', error);
        addLogEntryToUI({
            level: 'error',
            message: error.message,
            timestamp: new Date().toISOString()
        });
    }
}

// Add this function to update UI based on status
function updateUIStatus(status) {
    const sendBtn = document.getElementById('send-btn');
    
    if (status.isLoading) {
        sendBtn.disabled = true;
        sendBtn.innerHTML = `
            <span class="spinner"></span>
            ${status.progress || 'Sending...'} <button class="cancel-btn">Cancel</button>
        `;
    } else {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send Emails';
        
        if (status.error) {
            addLogEntryToUI({
                level: 'error',
                message: status.error,
                timestamp: new Date().toISOString()
            });
        } else if (status.progress) {
            addLogEntryToUI({
                level: 'success',
                message: status.progress,
                timestamp: new Date().toISOString()
            });
        }
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
            console.error(`SMTP ${field.replace('-', ' ')} is required`);
            switchTab('settings');
            return false;
        }
    }
    return true;
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
        logEntries.innerHTML = ''; // Clear existing logs

        if (data.logs && Array.isArray(data.logs)) {
            // Sort logs by timestamp in descending order
            const sortedLogs = data.logs.sort((a, b) =>
                new Date(b.timestamp) - new Date(a.timestamp)
            );

            // Add each log entry to the UI
            sortedLogs.forEach(log => addLogEntryToUI(log, false));
        }

    } catch (error) {
        console.error('Error loading logs:', error);
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

        await loadLogs(); // Reload logs after clearing

    } catch (error) {
        console.error('Error clearing logs:', error);
    }
}

async function loadEmailList() {
    try {
        // Try loading from backend first
        const response = await fetch(`${API_BASE_URL}/email-list`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (data.status === 'success') {
            const emailList = document.getElementById('email-list');
            emailList.value = data.emails.join('\n');
        }

        // Also load from local storage as backup
        const local = await chrome.storage.local.get(['emailList']);
        if (local.emailList && (!data.emails || data.emails.length === 0)) {
            const emailList = document.getElementById('email-list');
            emailList.value = local.emailList.join('\n');
        }
    } catch (error) {
        console.error('Error loading email list:', error);
        // Fallback to local storage
        const local = await chrome.storage.local.get(['emailList']);
        if (local.emailList) {
            const emailList = document.getElementById('email-list');
            emailList.value = local.emailList.join('\n');
        }
    }
}

async function saveEmailList() {
    try {
        const emailListText = document.getElementById('email-list').value;
        const emails = emailListText.split('\n').filter(email => email.trim());

        // Save to backend
        const response = await fetch(`${API_BASE_URL}/email-list`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({
                emails: emails
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Save to local storage
        await chrome.storage.local.set({ 
            emailList: emails,
            lastUpdated: new Date().toISOString()
        });
    } catch (error) {
        console.error('Error saving email list:', error);
    }
}

// Modified saveEmailTemplate function
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

        // Save to backend
        const response = await fetch(`${API_BASE_URL}/email-template`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({
                subject,
                body,
                attachments
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Save to local storage
        await chrome.storage.local.set({
            emailTemplate: {
                subject,
                body,
                attachments,
                lastUpdated: new Date().toISOString()
            }
        });
    } catch (error) {
        console.error('Error saving template:', error);
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
            console.info(`CSV Import Results:`);
            console.info(`- ${importCount} emails imported successfully`);
            if (duplicateCount > 0) {
                console.info(`- ${duplicateCount} duplicate emails skipped`);
            }
            if (invalidCount > 0) {
                console.error(`- ${invalidCount} invalid emails skipped`);
            }
        };

        reader.onerror = () => {
            throw new Error('Error reading CSV file');
        };

        reader.readAsText(file);
    } catch (error) {
        console.error('Error importing CSV:', error);
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Add some CSS for better log visualization
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .log-entry {
        padding: 8px;
        margin: 4px 0;
        border-radius: 4px;
        border-left: 4px solid #ccc;
        background-color: #f8f9fa;
    }
    
    .realtime-log {
        border-left-color: #4CAF50;
        background-color: #f1f8e9;
    }
    
    .log-timestamp {
        color: #666;
        margin-right: 8px;
        font-family: monospace;
    }
    
    .log-level {
        font-weight: bold;
        margin-right: 8px;
        text-transform: uppercase;
        font-size: 0.85em;
        padding: 2px 6px;
        border-radius: 3px;
    }
    
    .log-level.info { 
        color: #fff;
        background-color: #4CAF50; 
    }
    .log-level.error { 
        color: #fff;
        background-color: #f44336; 
    }
    .log-level.warning { 
        color: #fff;
        background-color: #ff9800; 
    }
    
    .log-message {
        color: #333;
        margin-left: 8px;
    }
    
    .log-details {
        display: block;
        margin-top: 4px;
        margin-left: 8px;
        color: #666;
        font-size: 0.9em;
        font-family: monospace;
        white-space: pre-wrap;
        background-color: #fff;
        padding: 4px 8px;
        border-radius: 3px;
        border: 1px solid #eee;
    }
`;
document.head.appendChild(style);