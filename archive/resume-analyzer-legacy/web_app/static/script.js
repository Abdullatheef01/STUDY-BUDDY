/**
 * AI Resume Analyzer - Frontend JavaScript
 * Handles file upload, animations, charts, and interactive elements.
 */

document.addEventListener('DOMContentLoaded', () => {
    initParticles();
    initNavbar();
    initUpload();
    initDashboardAnimations();
    initScrollReveal();
});

// ================================================
// PARTICLES
// ================================================
function initParticles() {
    const container = document.getElementById('particles');
    if (!container) return;

    const particleCount = 30;
    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        particle.classList.add('particle');
        particle.style.left = Math.random() * 100 + '%';
        particle.style.animationDelay = Math.random() * 8 + 's';
        particle.style.animationDuration = (6 + Math.random() * 6) + 's';
        
        const colors = ['#7c5cfc', '#00d4aa', '#ff6b9d', '#ffb347', '#54a0ff'];
        particle.style.background = colors[Math.floor(Math.random() * colors.length)];
        particle.style.width = (2 + Math.random() * 3) + 'px';
        particle.style.height = particle.style.width;
        
        container.appendChild(particle);
    }
}

// ================================================
// NAVBAR
// ================================================
function initNavbar() {
    const navbar = document.getElementById('navbar');
    if (!navbar) return;

    let lastScroll = 0;
    window.addEventListener('scroll', () => {
        const currentScroll = window.pageYOffset;
        if (currentScroll > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
        lastScroll = currentScroll;
    });
}

// ================================================
// FILE UPLOAD
// ================================================
function initUpload() {
    const uploadCard = document.getElementById('uploadCard');
    const fileInput = document.getElementById('fileInput');
    const fileSelected = document.getElementById('fileSelected');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const removeFile = document.getElementById('removeFile');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const uploadForm = document.getElementById('uploadForm');
    const errorMessage = document.getElementById('errorMessage');
    const errorText = document.getElementById('errorText');

    if (!uploadCard || !fileInput) return;

    // Click to upload
    uploadCard.addEventListener('click', (e) => {
        if (e.target === removeFile || e.target.closest('.remove-file')) return;
        if (e.target.closest('.file-selected')) return;
        fileInput.click();
    });

    // Drag & Drop
    uploadCard.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadCard.classList.add('drag-over');
    });

    uploadCard.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadCard.classList.remove('drag-over');
    });

    uploadCard.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadCard.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    // Remove file
    if (removeFile) {
        removeFile.addEventListener('click', (e) => {
            e.stopPropagation();
            clearFile();
        });
    }

    function handleFile(file) {
        const allowedTypes = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword'
        ];
        const allowedExts = ['.pdf', '.docx', '.doc'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();

        hideError();

        if (!allowedTypes.includes(file.type) && !allowedExts.includes(ext)) {
            showError('Please upload a PDF or DOCX file.');
            return;
        }

        if (file.size > 16 * 1024 * 1024) {
            showError('File is too large. Maximum size is 16MB.');
            return;
        }

        // Show file info
        fileName.textContent = file.name;
        fileSize.textContent = formatFileSize(file.size);
        fileSelected.classList.add('show');
        analyzeBtn.classList.add('show');

        // Update file input
        const dt = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;
    }

    function clearFile() {
        fileInput.value = '';
        fileSelected.classList.remove('show');
        analyzeBtn.classList.remove('show');
        hideError();
    }

    function showError(msg) {
        errorText.textContent = msg;
        errorMessage.classList.add('show');
    }

    function hideError() {
        errorMessage.classList.remove('show');
    }

    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    // Form submission
    if (uploadForm) {
        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            if (!fileInput.files.length) {
                showError('Please select a file first.');
                return;
            }

            // Show loading
            const loadingOverlay = document.getElementById('loadingOverlay');
            loadingOverlay.classList.add('show');
            analyzeBtn.disabled = true;

            // Animate loading steps
            animateLoadingSteps();

            // Submit form
            const formData = new FormData();
            formData.append('resume', fileInput.files[0]);

            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (data.success && data.redirect) {
                    // Complete all loading steps
                    completeAllSteps();
                    setTimeout(() => {
                        window.location.href = data.redirect;
                    }, 600);
                } else {
                    loadingOverlay.classList.remove('show');
                    analyzeBtn.disabled = false;
                    showError(data.error || 'Analysis failed. Please try again.');
                }
            } catch (err) {
                console.error('Upload error:', err);
                loadingOverlay.classList.remove('show');
                analyzeBtn.disabled = false;
                showError('Network error. Please check your connection and try again.');
            }
        });
    }
}

// ================================================
// LOADING ANIMATION
// ================================================
function animateLoadingSteps() {
    const steps = document.querySelectorAll('.loading-step');
    let currentStep = 0;

    function activateStep() {
        if (currentStep < steps.length) {
            // Mark previous as done
            if (currentStep > 0) {
                steps[currentStep - 1].classList.remove('active');
                steps[currentStep - 1].classList.add('done');
                steps[currentStep - 1].querySelector('.step-icon').textContent = '✅';
            }
            
            // Activate current
            steps[currentStep].classList.add('active');
            steps[currentStep].querySelector('.step-icon').textContent = '⚡';
            
            currentStep++;
            setTimeout(activateStep, 1500 + Math.random() * 1000);
        }
    }

    activateStep();
}

function completeAllSteps() {
    const steps = document.querySelectorAll('.loading-step');
    steps.forEach(step => {
        step.classList.remove('active');
        step.classList.add('done');
        step.querySelector('.step-icon').textContent = '✅';
    });
}

// ================================================
// DASHBOARD ANIMATIONS
// ================================================
function initDashboardAnimations() {
    // Animated counter
    const counters = document.querySelectorAll('.counter');
    counters.forEach(counter => {
        const target = parseFloat(counter.dataset.target);
        if (isNaN(target)) return;
        animateCounter(counter, 0, target, 2000);
    });

    // Score ring animation
    const progressCircle = document.querySelector('.progress-circle');
    if (progressCircle) {
        const percentage = parseFloat(progressCircle.dataset.percentage) || 0;
        const circumference = 2 * Math.PI * 90; // radius = 90
        const offset = circumference - (percentage / 100) * circumference;
        
        setTimeout(() => {
            progressCircle.style.strokeDashoffset = offset;
        }, 300);
    }

    // Breakdown bars
    const fills = document.querySelectorAll('.breakdown-fill, .match-fill');
    const fillObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const width = entry.target.dataset.width;
                if (width) {
                    setTimeout(() => {
                        entry.target.style.width = width + '%';
                    }, 300);
                }
                fillObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.3 });

    fills.forEach(fill => fillObserver.observe(fill));
}

function animateCounter(element, start, end, duration) {
    const startTime = performance.now();
    const isFloat = !Number.isInteger(end);

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Ease out cubic
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = start + (end - start) * easeOut;

        element.textContent = isFloat ? current.toFixed(1) : Math.round(current);

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

// ================================================
// SCROLL REVEAL
// ================================================
function initScrollReveal() {
    const revealElements = document.querySelectorAll('.feature-card, .dash-card, .full-section');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    revealElements.forEach(el => observer.observe(el));

    // Add visible class with stagger for dashboard cards
    const dashCards = document.querySelectorAll('.dash-card');
    dashCards.forEach((card, i) => {
        setTimeout(() => {
            card.classList.add('visible');
        }, 200 + i * 150);
    });

    const fullSections = document.querySelectorAll('.full-section');
    fullSections.forEach((section, i) => {
        setTimeout(() => {
            section.classList.add('visible');
        }, 400 + i * 200);
    });
}

// ================================================
// SMOOTH SCROLL
// ================================================
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});
