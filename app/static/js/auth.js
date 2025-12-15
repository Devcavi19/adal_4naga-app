// Check if user is already logged in
if (sessionStorage.getItem('access_token') && window.location.pathname !== '/chat') {
    window.location.href = '/chat';
}

// Handle email continue button
const emailContinueBtn = document.getElementById('email-continue-btn');
const backBtn = document.getElementById('back-btn');
const socialButtons = document.querySelector('.social-buttons');
const emailInputs = document.querySelector('.email-inputs');

if (emailContinueBtn) {
    emailContinueBtn.addEventListener('click', () => {
        socialButtons.classList.add('hidden');
        emailInputs.classList.remove('hidden');
    });
}

if (backBtn) {
    backBtn.addEventListener('click', () => {
        emailInputs.classList.add('hidden');
        socialButtons.classList.remove('hidden');
    });
}

// Toggle password visibility
function setupPasswordToggle(toggleBtnId, inputId) {
    const toggleBtn = document.getElementById(toggleBtnId);
    const passwordInput = document.getElementById(inputId);
    
    if (toggleBtn && passwordInput) {
        toggleBtn.addEventListener('click', () => {
            const type = passwordInput.type === 'password' ? 'text' : 'password';
            passwordInput.type = type;
            
            const icon = toggleBtn.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-eye');
                icon.classList.toggle('fa-eye-slash');
            }
        });
    }
}

// Show error message
function showError(message) {
    const errorDiv = document.getElementById('error-message');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        
        // Hide after 5 seconds
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 5000);
    }
}

// Show success message
function showSuccess(message) {
    const successDiv = document.getElementById('success-message');
    if (successDiv) {
        successDiv.textContent = message;
        successDiv.style.display = 'block';
    }
}

// Show loading state on button
function setButtonLoading(btnId, isLoading) {
    const btn = document.getElementById(btnId);
    if (btn) {
        const btnText = btn.querySelector('.btn-text');
        const btnLoader = btn.querySelector('.btn-loader');
        
        if (isLoading) {
            btn.disabled = true;
            btnText.style.display = 'none';
            btnLoader.style.display = 'inline-block';
        } else {
            btn.disabled = false;
            btnText.style.display = 'inline';
            btnLoader.style.display = 'none';
        }
    }
}

// Validate CSPC email
function isValidCSPCEmail(email) {
    return email.endsWith('@cspc.edu.ph') || email.endsWith('@my.cspc.edu.ph');
}

// Sign In Page
const signinForm = document.getElementById('signin-form');
if (signinForm) {
    setupPasswordToggle('toggle-password', 'password');
    
    signinForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const email = document.getElementById('email').value.trim();
        const password = document.getElementById('password').value;
        
        if (!email || !password) {
            showError('Please fill in all fields');
            return;
        }
        
        if (!isValidCSPCEmail(email)) {
            showError('Please use a valid CSPC email address (@cspc.edu.ph or @my.cspc.edu.ph)');
            return;
        }
        
        setButtonLoading('signin-btn', true);
        
        try {
            const response = await fetch('/api/auth/signin', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email, password })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Store session
                if (data.session) {
                    sessionStorage.setItem('access_token', data.session.access_token);
                }
                
                // Redirect to chat
                window.location.href = '/chat';
            } else {
                showError(data.error || 'Sign in failed');
                setButtonLoading('signin-btn', false);
            }
        } catch (error) {
            console.error('Sign in error:', error);
            showError('An error occurred. Please try again.');
            setButtonLoading('signin-btn', false);
        }
    });
}

// Sign Up Page
const signupForm = document.getElementById('signup-form');
if (signupForm) {
    setupPasswordToggle('toggle-password', 'password');
    setupPasswordToggle('toggle-confirm-password', 'confirm-password');
    
    signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const fullName = document.getElementById('full-name').value.trim();
        const email = document.getElementById('email').value.trim();
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirm-password').value;
        const terms = document.getElementById('terms').checked;
        
        // Validation
        if (!fullName || !email || !password || !confirmPassword) {
            showError('Please fill in all fields');
            return;
        }
        
        if (!isValidCSPCEmail(email)) {
            showError('Please use a valid CSPC email address (@cspc.edu.ph or @my.cspc.edu.ph)');
            return;
        }
        
        if (password.length < 8) {
            showError('Password must be at least 8 characters');
            return;
        }
        
        if (password !== confirmPassword) {
            showError('Passwords do not match');
            return;
        }
        
        if (!terms) {
            showError('Please agree to the Terms of Service and Privacy Policy');
            return;
        }
        
        setButtonLoading('signup-btn', true);
        
        try {
            const response = await fetch('/api/auth/signup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    full_name: fullName,
                    email, 
                    password 
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showSuccess(data.message || 'Account created! Please check your email to verify.');
                signupForm.reset();
                
                // Redirect to login after 3 seconds
                setTimeout(() => {
                    window.location.href = '/login';
                }, 3000);
            } else {
                showError(data.error || 'Sign up failed');
                setButtonLoading('signup-btn', false);
            }
        } catch (error) {
            console.error('Sign up error:', error);
            showError('An error occurred. Please try again.');
            setButtonLoading('signup-btn', false);
        }
    });
}

// Google Sign In/Up
const googleSigninBtn = document.getElementById('google-signin-btn');
const googleSignupBtn = document.getElementById('google-signup-btn');

async function handleGoogleAuth() {
    try {
        const response = await fetch('/api/auth/google');
        const data = await response.json();
        
        if (response.ok && data.url) {
            window.location.href = data.url;
        } else {
            showError('Google authentication failed');
        }
    } catch (error) {
        console.error('Google auth error:', error);
        showError('An error occurred with Google authentication');
    }
}

if (googleSigninBtn) {
    googleSigninBtn.addEventListener('click', handleGoogleAuth);
}

if (googleSignupBtn) {
    googleSignupBtn.addEventListener('click', handleGoogleAuth);
}

// Check for auth errors in URL
const urlParams = new URLSearchParams(window.location.search);
const error = urlParams.get('error');
if (error === 'auth_failed') {
    showError('Authentication failed. Please try again.');
}