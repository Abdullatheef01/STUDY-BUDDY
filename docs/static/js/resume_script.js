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
                // --- GitHub Pages Full Client-Side Mode ---
                if (window.location.hostname.includes('github.io')) {
                    console.log('Running in Full Client-Side Mode (GitHub Pages)');
                    
                    // 1. Extract Text from File
                    const file = fileInput.files[0];
                    let text = '';
                    
                    try {
                        updateLoadingStep(1, 'Extracting text from ' + file.name + '...');
                        if (file.type === 'application/pdf') {
                            text = await extractTextFromPDF(file);
                        } else if (file.name.endsWith('.docx')) {
                            text = await extractTextFromDOCX(file);
                        } else {
                            throw new Error('Unsupported file type');
                        }
                    } catch (err) {
                        throw new Error('Failed to extract text: ' + err.message);
                    }

                    if (!text || text.trim().length < 50) {
                        throw new Error('Could not extract enough text from the document.');
                    }

                    // 2. Run AI Analysis via Gemini
                    updateLoadingStep(2, 'Identifying skills & experience...');
                    updateLoadingStep(3, 'Running AI semantic analysis...');
                    
                    const analysisResult = await runGeminiAnalysis(text);
                    
                    // 3. Save result to session storage and redirect
                    updateLoadingStep(4, 'Calculating ATS score...');
                    updateLoadingStep(5, 'Generating recommendations...');
                    
                    sessionStorage.setItem('last_analysis', JSON.stringify(analysisResult));
                    
                    completeAllSteps();
                    setTimeout(() => {
                        window.location.href = 'dashboard.html';
                    }, 800);
                    return;
                }

                // --- Real Backend Mode (Localhost) ---
                const response = await fetch('/analyze', {
                    method: 'POST',
                    body: formData
                });
                // ... (rest of the original backend logic)

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
                
                // Show the actual error message to the user
                showError(err.message || 'An unexpected error occurred. Please try again.');
            }
        });
    }
}

// ================================================
// LOADING ANIMATION
// ================================================
let loadingTimer;
let isAnalysisComplete = false;

function animateLoadingSteps() {
    isAnalysisComplete = false;
    const steps = document.querySelectorAll('.loading-step');
    let currentStep = 0;

    // Reset all steps first
    steps.forEach(step => {
        step.classList.remove('active', 'done');
        step.querySelector('.step-icon').textContent = '⏳';
    });

    function activateStep() {
        if (isAnalysisComplete) return;

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
            loadingTimer = setTimeout(activateStep, 1500 + Math.random() * 1000);
        }
    }

    activateStep();
}

function completeAllSteps() {
    isAnalysisComplete = true;
    clearTimeout(loadingTimer);
    
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
// ================================================
// CLIENT-SIDE PARSING & AI (GITHUB PAGES)
// ================================================

function updateLoadingStep(stepNum, text) {
    const step = document.querySelector(`.loading-step[data-step="${stepNum}"]`);
    if (step) {
        step.classList.add('active');
        step.querySelector('span:last-child').textContent = text;
    }
    const loadingText = document.querySelector('.loading-text');
    if (loadingText) loadingText.textContent = text;
}

function saveApiKey() {
    const key = document.getElementById('apiKeyInput').value.trim();
    if (key) {
        localStorage.setItem('GEMINI_API_KEY', key);
        document.getElementById('apiModal').style.display = 'none';
        if (window.onApiKeySave) window.onApiKeySave(key);
    } else {
        alert('Please enter a valid API key.');
    }
}

function closeApiModal() {
    document.getElementById('apiModal').style.display = 'none';
    if (window.onApiKeyCancel) window.onApiKeyCancel();
}

async function extractTextFromPDF(file) {
    console.log('Starting PDF extraction...');
    const arrayBuffer = await file.arrayBuffer();
    
    // Use window.pdfjsLib which is standard for the CDN version
    const pdfjsLib = window['pdfjsLib'] || window['pdfjs-dist/build/pdf'];
    if (!pdfjsLib) throw new Error('PDF library not loaded correctly.');
    
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';
    
    try {
        const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        let fullText = '';
        
        for (let i = 1; i <= pdf.numPages; i++) {
            const page = await pdf.getPage(i);
            const textContent = await page.getTextContent();
            const pageText = textContent.items.map(item => item.str).join(' ');
            fullText += pageText + '\n';
        }
        
        console.log('PDF extraction complete. Text length:', fullText.length);
        return fullText;
    } catch (err) {
        console.error('PDF JS Error:', err);
        throw new Error('Error parsing PDF file: ' + err.message);
    }
}

async function extractTextFromDOCX(file) {
    const arrayBuffer = await file.arrayBuffer();
    const result = await mammoth.extractRawText({ arrayBuffer: arrayBuffer });
    return result.value;
}

async function runGeminiAnalysis(resumeText) {
    let apiKey = localStorage.getItem('GEMINI_API_KEY');
    
    if (!apiKey) {
        // Hide general loading and show API modal
        document.getElementById('loadingOverlay').classList.remove('show');
        document.getElementById('apiModal').style.display = 'flex';
        
        // Wait for user to save the key
        apiKey = await new Promise((resolve) => {
            window.onApiKeySave = (key) => resolve(key);
            window.onApiKeyCancel = () => resolve(null);
        });

        // Re-show loading if we got a key
        if (apiKey) {
            document.getElementById('loadingOverlay').classList.add('show');
        }
    }
    
    if (!apiKey) throw new Error('API Key is required for analysis on GitHub Pages.');

    // ... (rest of the prompt logic remains the same)

    const promptText = `
    Analyze this resume text and provide a professional career analysis in JSON format.
    
    RESUME TEXT:
    ${resumeText.substring(0, 10000)}
    
    REQUIRED JSON STRUCTURE:
    {
        "summary": "Short professional summary",
        "ats": {
            "percentage": number (0-100),
            "grade": "A/B/C/D",
            "grade_label": "Excellent/Good/Average/Poor",
            "breakdown": {
                "skills": {"label": "Skill Matching", "score": number, "max": 30, "details": "..."},
                "experience": {"label": "Experience Relevance", "score": number, "max": 25, "details": "..."}
            }
        },
        "skills": ["skill1", "skill2", ...],
        "skills_by_category": {"Languages": [...], "Frameworks": [...], ...},
        "feedback": [{"title": "...", "suggestion": "...", "priority": "High/Medium/Low", "icon": "📈", "impact": "..."}],
        "recommendations": [{"title": "Job Title", "company": "Company", "match_score": number, "fit_level": "...", "fit_color": "#...", "location": "...", "experience_level": "...", "salary_range": "...", "posted_date": "...", "skill_match_percent": number, "matched_skills": [...], "missing_skills": [...]}],
        "skill_gaps": {"summary": "...", "critical": [{"skill": "...", "demanded_by": number}], "important": [], "nice_to_have": []},
        "career_paths": [{"path": "...", "icon": "🚀", "industry_demand": "High", "match_percentage": number, "progression": ["Level 1", "Level 2", ...], "current_level": "...", "next_level": "..."}],
        "roadmap": [{"order": 1, "skill": "...", "why": "...", "estimated_time": "...", "resources": ["..."]}],
        "total_learning_time": "...",
        "interview_questions": {"role": "...", "technical": [...], "behavioral": [...], "system_design": [...]}
    }
    
    Return ONLY raw JSON. No markdown formatting.
    `;

    try {
        const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                contents: [{ parts: [{ text: promptText }] }]
            })
        });

        const data = await response.json();
        if (data.error) throw new Error(data.error.message);
        
        let jsonText = data.candidates[0].content.parts[0].text;
        // Clean markdown
        jsonText = jsonText.replace(/```json/g, '').replace(/```/g, '').trim();
        
        return JSON.parse(jsonText);
    } catch (err) {
        if (err.message.includes('API_KEY_INVALID')) {
            localStorage.removeItem('GEMINI_API_KEY');
            throw new Error('Invalid API Key. Please try again.');
        }
        throw err;
    }
}

