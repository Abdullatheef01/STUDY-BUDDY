# Frontend Documentation: AI Resume Analyzer Features

## 🎨 Design Philosophy: "Vibrant & Premium"
The frontend is built using a "Glassmorphism" aesthetic, aimed at delivering a professional yet high-energy experience. The UI avoids dull browser defaults, opting instead for a custom design system built with vanilla HTML, CSS, and modern JavaScript.

### Key Visual Elements:
- **Dynamic Background**: A fixed, animated background with orbiting blur circles (Orbs) in accent colors.
- **Particle System**: A lightweight JavaScript-powered particle system that adds subtle movement to the hero section.
- **Gradients**: Consistent use of HSL-tailored gradients (Primary: Purple to Teal; Secondary: Pink to Gold).
- **Glassmorphism**: Translucent cards with `backdrop-filter: blur(20px)` and subtle white borders (15% opacity).

## ✨ Core UI Features

### 1. Unified Upload Experience
- **Drag-and-Drop**: Interactive upload zone with `drag-over` state detections.
- **Multi-Step Loading**: A custom loading overlay that shows real-time analysis progress ("Extracting text", "Running BERT", etc.) using micro-animations.
- **File Validation**: Instant frontend validation for file type and size (max 16MB).

### 2. Analysis Dashboard
The dashboard is designed for high-data density without overwhelming the user:
- **Interactive Score Ring**: A SVG-based circular progress bar that animates from 0 to the final ATS score.
- **Skill Tags**: Categorized skill tags (Languages, Frameworks, Tools) with a popping entry animation.
- **Job Cards**: Hover-animated cards showing a match percentage, skill-fit badges (Matched/Missing), and estimated salary.
- **Intersection Observer**: Content reveals itself smoothly as the user scrolls, preventing a "static" feel.
- **Priority Feedback**: Resume improvement suggestions color-coded by priority (High: Red, Medium: Orange, Low: Blue).

### 3. Interview Preparation Hub
A dedicated page for interview readiness:
- **Tabbed Navigation**: Instant switching between "Interview Questions" and "Coding Practice" without page reloads.
- **Company Grid**: Animated cards for 20+ top tech companies (Google, Amazon, Meta, etc.).
- **Dynamic Filters**: Real-time filtering by Difficulty (Easy, Medium, Hard) and Category/Topic.
- **Solving Links**: Direct integration with external platforms (like LeetCode) for coding problems.

## ⚡ Performance Optimizations
- **No External Frameworks**: Zero dependency on heavy libraries like Bootstrap or Tailwind, resulting in near-instant paint times.
- **GPU Acceleration**: Animations use `transform` and `opacity` properties to ensure a smooth 60FPS experience.
- **Iconography**: Uses high-impact Unicode emojis and SVG graphics to avoid external asset loading latencies.

## 📱 Responsiveness
The UI uses a `clamp()` based typography system and CSS Grid `auto-fit` layouts, ensuring the dashboard looks equally stunning on high-res monitors and mobile devices.
