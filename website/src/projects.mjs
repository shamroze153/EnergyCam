// Projects shown on /projects.html and on the homepage.
// To add a project: copy one entry, change the fields, put its cover image in
// src/assets/img/projects/ (1600x1000 works well), then run `node build.mjs`.
// Newest first. `service` must be one of: vision, twin, agents, portal, energy.

export const PROJECTS = [
  {
    slug: 'energycam',
    title: 'EnergyCam',
    service: 'vision',
    year: '2026',
    status: 'Built and running',
    summary: 'CCTV that catches ACs running in empty rooms. It counts people with YOLOv8, checks each AC, and emails the facilities team a snapshot after 10 seconds of waste.',
    image: 'assets/img/scenes/vision-s.jpg',
    points: [
      'Runs on existing IP cameras over RTSP',
      'Two ACs per room, readings smoothed over four frames',
      'Alert and "resolved" emails with a snapshot',
      'Live dashboard with waste cost in rupees',
    ],
    tags: ['YOLOv8', 'OpenCV', 'PostgreSQL', 'Streamlit'],
    links: [
      { label: 'Read the build log', href: 'logs.html#log-01' },
      { label: 'Computer vision service', href: 'services/computer-vision.html' },
    ],
  },
  {
    slug: 'services-3d',
    title: 'Mimar AI in 3D',
    service: 'twin',
    year: '2026',
    status: 'Live on this site',
    summary: 'Interactive 3D scenes that show five building problems and the system that fixes each one, built with three.js and rendered in the browser.',
    image: 'assets/img/scenes/twin-s.jpg',
    points: [
      'Five problem-to-solution scenes',
      'An interactive building with a hotspot per service',
      'Runs on phones, with a still image fallback',
    ],
    tags: ['three.js', 'WebGL'],
    links: [{ label: 'Open the 3D experience', href: 'experience.html' }],
  },
];
