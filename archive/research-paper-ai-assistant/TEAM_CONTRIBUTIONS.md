# 📋 Project Team Contributions

## Research Paper AI Assistant — Team Division

**Course**: Frontend Web Development  
**Project**: Research Paper AI Assistant (PaperAI)

---

## 👥 Team Members

| #  | Name              | Role                          |
|----|-------------------|-------------------------------|
| 1  | **Vivek Bartwal**  | Team Lead & Core Architecture |
| 2  | **Divyansh**       | Constructor Module Developer  |
| 3  | **Tanmay**         | Deconstructor Module Developer|
| 4  | **Manav**          | UI/UX Design & Styling        |

---

## 🧩 Detailed Contribution Breakdown

---

### 🟣 Vivek Bartwal — Team Lead & Core Architecture

**Responsibility**: Project setup, SPA navigation system, overall architecture, PDF generation engine, and project integration.

**Files Worked On**:
- `index.html` — Core HTML structure, `<head>` setup, navigation bar, and SPA section scaffolding (Lines 1–46, 199–212)
- `app.js` — SPA navigation logic, routing system, hash handling, and page-switching engine (Lines 1–46)
- `app.js` — IEEE PDF Generation Engine: 3-page professional academic PDF with Times New Roman fonts, two-column layout, abstract, introduction, literature review, system architecture, methodology, results, conclusion, and Constructor Dashboard (Lines 450–629)
- `PROJECT_OVERVIEW.md` — Complete project documentation
- `README.md` — Project readme and setup instructions
- Project integration, testing, and deployment coordination

**Key Contributions**:
1. Designed the **Single Page Application (SPA)** architecture using vanilla JavaScript with `history.pushState` for seamless navigation without page reloads.
2. Built the **IEEE PDF Generation Engine** using jsPDF — a 3-page professional research paper with:
   - Formal header with title and author metadata
   - Abstract and Keywords sections
   - Two-column body layout (Introduction, Literature Review, Design Philosophy, Architecture, Methodology)
   - Results and Conclusion sections
   - Dark-themed Constructor Summary Dashboard with metrics grid
3. Integrated all team members' modules into the final unified application.
4. Wrote project documentation including `PROJECT_OVERVIEW.md` and `README.md`.

---

### 🔵 Divyansh — Constructor Module Developer

**Responsibility**: GitHub repository analysis engine, constructor form logic, processing pipeline simulation, and dynamic content generation.

**Files Worked On**:
- `index.html` — Constructor section HTML: form container with input fields (repo URL, author name, institution), processing terminal with step indicators, and result preview area with structured sections (Lines 75–154)
- `app.js` — Constructor form submission logic, step-by-step processing simulation with async/await timing, and result population (Lines 48–109)
- `app.js` — `generateRepoSpecificContent()` Dynamic Content Engine: URL-based hashing for stable stats, dynamic abstract/architecture/methodology/conclusion generation with repo-specific context (Lines 111–135)

**Key Contributions**:
1. Designed the **Constructor Processing Terminal** — a 4-step simulation pipeline:
   - Step 1: Fetching Repository Source (1.5s)
   - Step 2: Building Vector Knowledge Base (2.0s)
   - Step 3: AI Architecture Analysis (1.8s)
   - Step 4: Drafting IEEE Paper (2.5s)
2. Built the **Dynamic Content Engine** (`generateRepoSpecificContent`) that extracts repo name and owner from the GitHub URL and generates unique, context-aware academic content (abstract, architecture analysis, methodology, conclusion).
3. Implemented a **deterministic hashing function** so that the same repository URL always produces consistent stats (file count, complexity rating, AI confidence).
4. Created the **Result Preview Panel** with structured sections for Abstract, Architecture, and Methodology, plus a statistics bar showing Files Indexed, Complexity, and AI Confidence.

---

### 🟢 Tanmay — Deconstructor Module Developer

**Responsibility**: Smart chat system, file upload with context extraction, AI response engine, session management, and typing indicator.

**Files Worked On**:
- `index.html` — Deconstructor section HTML: chat sidebar with session list, upload zone with drag-and-drop, chat messaging interface, typing indicator element (Lines 156–198)
- `app.js` — `extractTopicFromFiles()` context extraction engine (Lines 155–175)
- `app.js` — `generateDeconstructorResponse()` keyword-based intelligent AI response engine with 8 specialized response categories (Lines 178–260)
- `app.js` — File upload handler with context-aware indexing simulation, drag-and-drop system, message system, typing indicator show/hide, and smart send message logic (Lines 263–375)
- `app.js` — Session management: session switching, New Session (+) button with upload state reset and dynamic sidebar updates (Lines 378–449)

**Key Contributions**:
1. Implemented **Context-Aware File Upload** — extracts the topic from uploaded PDF filenames, creating a rich context object with topic name, keywords, page estimates, and citation counts.
2. Built the **Dynamic AI Response Engine** (`generateDeconstructorResponse`) that matches user queries against 8 intelligent categories:
   - Topic/Summary, Methodology, Results/Findings, Conclusion/Future Work
   - Author Info, Citations/References, Abstract/Introduction, Comparative Analysis
3. Created the **Typing Indicator** — animated bouncing dots that appear while the AI is "synthesizing" a response with realistic 1–2.5s delay.
4. Implemented full **Session Management**: 
   - Session switching between research tracks
   - "New Session" (+) button that resets chat, clears context, and re-creates the upload interface
   - Dynamic sidebar updates showing the name of the currently loaded paper

---

### 🟡 Manav — UI/UX Design & Styling

**Responsibility**: Complete visual design system, CSS architecture, animations, responsive layout, and premium aesthetics.

**Files Worked On**:
- `index.css` — Complete CSS design system (All 840+ lines):
  - CSS Custom Properties / Design Tokens (Lines 1–35)
  - Animated Background with glow orbs and wave SVG (Lines 45–110)
  - Navigation bar with glassmorphism and hover effects (Lines 112–175)
  - Hero section with gradient text and staggered animations (Lines 177–230)
  - Feature cards with hover scale and glass effect (Lines 232–290)
  - Constructor section: form container, input styling, processing terminal with step animations, and result preview cards (Lines 292–565)
  - Deconstructor section: chat sidebar, upload zone with drag-and-drop styling, message bubbles (user/system), chat input area (Lines 567–730)
  - Typing indicator animation with keyframes (Lines 762–810)
  - Paper context badge with gradient background (Lines 812–830)
  - Utility classes, stagger-entry animations, footer, and responsive breakpoints (Lines 732–845)

**Key Contributions**:
1. Created the **"Midnight Neon" Design System** with CSS custom properties:
   - Color palette: Deep Navy (`#0a0f1c`), Electric Indigo (`#6366f1`), Magenta Flash (`#ec4899`), Cyan Accent (`#22d3ee`)
   - Typography: Outfit (headings) + Inter (body) from Google Fonts
   - Spacing, radius, and transition tokens for consistency
2. Designed the **Animated Background** with three floating glow orbs using CSS `@keyframes` and blur filters, plus an SVG wave effect at the bottom.
3. Implemented **Glassmorphism** across all panels using `backdrop-filter: blur()` with translucent borders and background overlays.
4. Built **Micro-Animations**: stagger-entry slide-ups, hover scale effects on cards, pulsing step indicators, gradient text shimmer, and the typing indicator bounce.
5. Ensured full **Responsive Design** with media queries for mobile (≤768px), including collapsible sidebar and adaptive grid layouts.

---

## 📁 File Ownership Summary

| File               | Vivek         | Divyansh      | Tanmay        | Manav         |
|--------------------|:---:|:---:|:---:|:---:|
| `index.html`       | Nav + Head    | Constructor   | Deconstructor | —             |
| `index.css`        | —             | —             | —             | ✅ Full Owner  |
| `app.js`           | SPA Nav + PDF | Constructor Logic | Deconstructor Logic | —     |
| `PROJECT_OVERVIEW.md` | ✅ Full Owner | —          | —             | —             |
| `README.md`        | ✅ Full Owner  | —            | —             | —             |

---

## 🛠️ Technology Stack (Individual Usage)

| Technology          | Used By                          |
|--------------------|----------------------------------|
| HTML5 (Semantic)    | Vivek, Divyansh, Tanmay         |
| CSS3 (Animations)   | Manav                           |
| Vanilla JavaScript  | Vivek, Divyansh, Tanmay         |
| jsPDF Library       | Vivek                           |
| Google Fonts API    | Manav                           |
| CSS Custom Properties | Manav                         |
| CSS Glassmorphism   | Manav                           |
| Git & GitHub        | Vivek (Integration Lead)        |

---

*Project completed as part of Frontend Web Development coursework.*
