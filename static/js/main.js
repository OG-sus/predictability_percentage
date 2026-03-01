document.addEventListener('DOMContentLoaded', () => {
    // --- Auth Modal Logic ---
    const authModal = document.getElementById('auth-modal');
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const resetForm = document.getElementById('reset-form');
    const authSuccess = document.getElementById('auth-success');

    function openAuthModal(mode) {
        if (authModal) {
            authModal.classList.add('visible');
            switchTab(mode);
        }
    }

    function closeAuthModal() {
        if (authModal) {
            authModal.classList.remove('visible');
        }
    }

    function switchTab(mode) {
        // Hide all forms
        document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
        // Reset tabs
        document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));

        if (mode === 'login' || mode === 'register') {
            const tab = document.getElementById(`tab-${mode}`);
            const form = document.getElementById(`${mode}-form`);
            if(tab) tab.classList.add('active');
            if(form) form.classList.add('active');
            const authTabs = document.querySelector('.auth-tabs');
            if(authTabs) authTabs.style.display = 'flex';
        } else if (mode === 'reset') {
            if(resetForm) resetForm.classList.add('active');
            const authTabs = document.querySelector('.auth-tabs');
            if(authTabs) authTabs.style.display = 'none';
        } else if (mode === 'success') {
            if(authSuccess) authSuccess.classList.add('active');
            const authTabs = document.querySelector('.auth-tabs');
            if(authTabs) authTabs.style.display = 'none';
        }

        // Clear errors
        document.querySelectorAll('.error-msg').forEach(e => e.textContent = '');
    }

    async function handleAuth(event, endpoint) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        const errorDiv = document.getElementById(`${endpoint}-error`);

        try {
            const response = await fetch(`/api/${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (response.ok) {
                if (endpoint === 'register') {
                    document.getElementById('success-msg').textContent = 'Account created successfully.';
                    document.getElementById('recovery-display').textContent = result.recovery_key;
                    document.getElementById('recovery-section').style.display = 'block';
                    document.getElementById('reset-success-btn').style.display = 'none';
                    switchTab('success');
                } else if (endpoint === 'reset_password') {
                    document.getElementById('success-msg').textContent = 'Password reset successfully.';
                    document.getElementById('recovery-section').style.display = 'none';
                    document.getElementById('reset-success-btn').style.display = 'block';
                    switchTab('success');
                } else {
                    window.location.href = '/calculator';
                }
            } else {
                if(errorDiv) errorDiv.textContent = result.error || 'Authentication failed.';
            }
        } catch (err) {
            if(errorDiv) errorDiv.textContent = 'Server error. Please try again.';
        }
    }

    // --- Event Listeners ---
    document.body.addEventListener('click', function(event) {
        // --- Modal Triggers ---
        if (event.target.matches('[onclick*="openAuthModal"]')) {
            const mode = event.target.getAttribute('onclick').includes('register') ? 'register' : 'login';
            openAuthModal(mode);
        }
        if (event.target.matches('.close-modal')) {
            closeAuthModal();
        }
        if (event.target.matches('.modal-overlay')) {
            closeAuthModal();
        }
        if (event.target.matches('[onclick*="switchTab"]')) {
             const mode = event.target.getAttribute('onclick').match(/'([^']+)'/)[1];
             switchTab(mode);
        }
    });
    
    // --- Form Submissions ---
    if(loginForm) loginForm.addEventListener('submit', (e) => handleAuth(e, 'login'));
    if(registerForm) registerForm.addEventListener('submit', (e) => handleAuth(e, 'register'));
    if(resetForm) resetForm.addEventListener('submit', (e) => handleAuth(e, 'reset_password'));
});
