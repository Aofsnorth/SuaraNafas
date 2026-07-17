# Asset Disclosure Log

This project uses the following assets. All AI-generated or third-party materials must be documented here before being used in production.

## AI-Generated Assets

| Asset | Source / Tool | Prompt / Notes | Used In |
|-------|---------------|----------------|---------|
| `assets/chatgpt-image/image.png` | Unknown legacy source; exact tool/model not recorded | Prompt metadata was not recorded. Retained as an unused design exploration and not rendered in production. | Not used |
| `public/images/test_xai_output.png` | User-supplied experiment output | XAI visualization supplied for the landing-page science narrative. Exact model and generation metadata were not recorded. | Landing page `Science` section |

## Third-Party Assets

- **3D Lung Model**: `lung.glb` sourced from the [Human Reference Atlas 3D Reference Object Library](https://humanatlas.io/3d-reference-library) / NIH Visible Human Male dataset, via the `cns-iu/hra-amap` repository. License: CC-BY 4.0.
- **Fonts**: Fraunces, Geist, JetBrains Mono via `next/font/google`.
- **3D Runtime**: Three.js, React Three Fiber, Drei.
- **Animation**: Framer Motion.
- **Navbar Design Reference**: `assets/navbar-galery/desktop.webp`, supplied by the user as a public inspiration reference. The implementation extracts only layout DNA; it does not ship or reproduce the reference image.
- **Icons**: No external icon library loaded. The current design does not use icons.

## Disclosures

- The 3D lung visualization is a research/educational model and is used here for demonstration only.
- The platform is a hackathon prototype and does not provide medical diagnosis.
- Third-party asset attribution is shown on `/transparency` and in the site footer.
- The navbar reference remains a design-study asset and is not rendered in production.
