import config from './config.js';
const { API_BASE_URL } = config;

document.addEventListener('DOMContentLoaded', () => {
    const loginSection = document.getElementById('login-section');
    const registerSection = document.getElementById('register-section');
    const showRegisterLink = document.getElementById('show-register');
    const showLoginLink = document.getElementById('show-login');

    // Check if user is already logged in
    const token = localStorage.getItem('token');
    if (token) {
        window.location.href = 'popup.html';
        return;
    }

    // Toggle between login and register
    showRegisterLink.addEventListener('click', (e) => {
        e.preventDefault();
        loginSection.classList.remove('active');
        registerSection.classList.add('active');
    });

    showLoginLink.addEventListener('click', (e) => {
        e.preventDefault();
        registerSection.classList.remove('active');
        loginSection.classList.add('active');
    });

    // Handle login form submission
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;

        console.log('Attempting login with:', { email }); // Debug log

        try {
            const response = await fetch(`${API_BASE_URL}/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email, password }),
                credentials: 'include' // Include cookies if needed
            });

            console.log('Login response:', response); // Debug log

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Login data:', data); // Debug log
            
            if (data.status === 'success') {
                localStorage.setItem('token', data.token);
                window.location.href = 'popup.html';
            } else {
                alert(data.message || 'Login failed');
            }
        } catch (error) {
            console.error('Login error:', error);
            alert('Login failed: ' + error.message);
        }
    });

    // Handle register form submission
    document.getElementById('register-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('register-email').value;
        const password = document.getElementById('register-password').value;
        const confirmPassword = document.getElementById('confirm-password').value;

        if (password !== confirmPassword) {
            alert('Passwords do not match');
            return;
        }

        console.log('Attempting registration with:', { email }); // Debug log

        try {
            const response = await fetch(`${API_BASE_URL}/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email, password }),
                credentials: 'include' // Include cookies if needed
            });

            console.log('Register response:', response); // Debug log

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Register data:', data); // Debug log
            
            if (data.status === 'success') {
                alert('Registration successful! Please login.');
                registerSection.classList.remove('active');
                loginSection.classList.add('active');
            } else {
                alert(data.message || 'Registration failed');
            }
        } catch (error) {
            console.error('Registration error:', error);
            alert('Registration failed: ' + error.message);
        }
    });

    // Ensure login section is visible by default
    loginSection.classList.add('active');
    registerSection.classList.remove('active');
});