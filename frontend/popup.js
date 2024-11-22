const API_BASE_URL = 'http://localhost:5000';

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

        addLogEntry('Starting email send process...', 'info');
        addLogEntry(`Preparing to send to ${emailList.length} recipients...`, 'info');

        const emailData = {
            emails: emailList,
            subject: subject,
            body: body
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