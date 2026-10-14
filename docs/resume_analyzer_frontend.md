# Resume Analyzer: Frontend Implementation

This module handles resume uploads, ATS score visualization, and semantic job matching.

## 1. Interface (`templates/resume_index.html`)
The main dashboard for career guidance and resume analysis.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <title>AI Resume Analyzer</title>
    <link rel="stylesheet" href="/static/css/resume_style.css">
</head>
<body>
    <!-- Hero, Upload Section, and Feature Highlights -->
</body>
</html>
```

## 2. Interaction Logic (`static/js/resume_script.js`)
Manages file drops, loading state animations, and the intersection observer for scroll reveals.

```javascript
document.addEventListener('DOMContentLoaded', () => {
    initParticles();
    initUpload();
    // ...
});
```

## 3. Premium Styles (`static/css/resume_style.css`)
The design system for the career platform, featuring gradient buttons and score rings.

```css
:root {
    --bg-primary: #0a0a1a;
    --accent-primary: #7c5cfc;
    --gradient-primary: linear-gradient(135deg, #7c5cfc 0%, #00d4aa 100%);
}
```

> [!TIP]
> The Resume module uses BERT-based semantic features which are visually represented through the dynamic match bars in the results dashboard.
