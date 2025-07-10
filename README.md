# EcosystemPlus Carbon Modelling System

A modern, farmer-friendly platform for calculating, visualizing, and reporting agricultural carbon emissions in Cameroon.  
**Tech stack:** Django REST API + Vue.js 3 frontend + Tailwind CSS + Chart.js + jsPDF + AOS + GSAP + Lucide + Particles.js + Swiper.

---

## Features

- **Accurate Carbon Calculations:** IPCC-compliant, Cameroon-adapted emission factors for fertilizer, livestock, and fuel.
- **Modern UI:** Vue 3 + Tailwind CSS for a clean, mobile-friendly experience.
- **Beautiful Charts:** Interactive, smooth bar charts with Chart.js.
- **PDF Reports:** Download professional, branded PDF reports of your results.
- **Farmer-Friendly:** Simple language, tooltips, and educational content.
- **Seasonal Awareness:** Emissions adjust for rainy/dry season automatically.
- **Personalized Recommendations:** Actionable tips to reduce your carbon footprint.

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+ (for advanced frontend dev, not required for CDN-only use)
- npm 8+ (for advanced frontend dev)
- Git

### Backend (Django)

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend (Vue.js)

- Open `frontend/index.html` directly in your browser (uses CDN for all dependencies).
- For advanced dev: `cd frontend && npm install` (optional).

---

## Project Structure

```
CARBON_MODELLING_V2/
├── carbon_backend/          # Django project settings
├── carbon_calculator/       # Main Django app
├── frontend/               # Vue.js frontend
│   ├── index.html         # Main frontend file
│   ├── package.json       # Node dependencies
│   ├── .eslintrc.js       # ESLint configuration
│   └── .prettierrc        # Prettier configuration
├── manage.py              # Django management script
├── requirements.txt       # Python dependencies

├── .flake8              # Flake8 configuration

└── README.md            # This file
```

## Current Status

- ✅ Repository audited and analyzed
- ✅ Python/Django environment confirmed working
- ✅ Node.js tooling available for Vue builds
- ✅ Backend tests pass (0 tests currently defined)
- ✅ Django development server functional
- ✅ Git branches created for parallel development
- ✅ Code formatting tools configured (Black, flake8, Prettier, ESLint)
- ✅ Development environment documented

## Next Steps

- Run `python manage.py runserver` to launch backend
- Open `frontend/index.html` to view current UI
- Identify layout/spacing issues for UI improvements
- Begin development on respective branches