# Research Paper Analyzer: Frontend Implementation

This module provides the interface for both the **IEEE Paper Constructor** and the **RAG-powered Deconstructor**.

## 1. Interface (`templates/research.html`)
The main layout utilizes a Glassmorphism design with a fixed animated background and radial glows.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Research Paper AI Assistant | Premium AI Tools</title>
    <link rel="stylesheet" href="/static/css/research_style.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.0/marked.min.js"></script>
</head>
<body>
    <!-- Navigation and Content Sections (Home, Constructor, Deconstructor) -->
    <!-- ... (Refers to full source code below) ... -->
</body>
</html>
```

## 2. Technical Logic (`static/js/research_app.js`)
Handles asynchronous API calls, PDF text extraction, and professional IEEE PDF generation.

```javascript
document.addEventListener('DOMContentLoaded', () => {
    // Navigation, AI Paper Generation, and Document-Grounded Chat Logic
    // ...
});
```

## 3. Design System (`static/css/research_style.css`)
Implements the 'Midnight Neon' aesthetic with backdrop filters and CSS animations.

```css
:root {
    --bg-dark: #0a0b1e;
    --primary: #6366f1;
    --accent: #22d3ee;
}
/* Glassmorphism and Layout Styles */
```

> [!NOTE]
> The full source code for these files is located in the repository under their respective paths.
